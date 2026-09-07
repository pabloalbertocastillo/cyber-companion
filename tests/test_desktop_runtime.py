"""Runtime contracts: temporal behavior, persistence failures and real Unix IPC."""
import asyncio
import copy
import json
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cyber_companion.assistant import LocalAssistant, evidence
from cyber_companion.core.events import EventV2, DeliveryClass, PrivacyClass, RetentionClass
from cyber_companion.core.model import Model, validate_sample
from cyber_companion.core.store import Store
from cyber_companion.core.validation import decode, encode
from cyber_companion.daemon import Daemon
from cyber_companion.ipc import Server, call
from cyber_companion.settings import Settings
from cyber_companion.ui.animation import Animation
from cyber_companion import sensors


def sample(cpu=.2, memory=.3, temperature=50, sensor="coretemp/Package"):
    return dict(cpu_ratio=cpu, memory_ratio=memory, temperature_c=temperature,
                temperature_limit_c=85, sensor=sensor, psi_cpu=0., psi_memory=0., psi_io=0.)


class BoundaryTests(unittest.TestCase):
    def event(self, data, **extra):
        args = dict(event_type="system.observed", source="sensor://system/local", subject="host/local",
                    sequence=1, schema="cc.system.observation@1", privacy=PrivacyClass.LOCAL_PRIVATE,
                    delivery=DeliveryClass.ORDERED, retention=RetentionClass.EPHEMERAL, data=data)
        args.update(extra)
        return EventV2.create(**args)

    def test_nested_event_payload_is_detached_and_immutable(self):
        value = {"players": [{"name": "one"}]}
        event = self.event(value)
        value["players"][0]["name"] = "changed"
        self.assertEqual(event.as_dict()["data"]["players"][0]["name"], "one")
        with self.assertRaises(TypeError):
            event.data["players"][0]["name"] = "unsafe"
        exported = event.as_dict()
        exported["data"]["players"].append("another")
        self.assertEqual(len(event.data["players"]), 1)

    def test_json_rejects_ambiguous_unbounded_and_nonfinite_values(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '[' * 18 + '0' + ']' * 18, '"' + 'x'*65537 + '"'):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                decode(raw)
        for kwargs in (dict(sequence=True), dict(ttl_ms=True), dict(privacy="local"), dict(privacy="secret")):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.event({}, **kwargs)

    def test_domain_schema_refuses_missing_boolean_ratio_and_oversize_text(self):
        for value in ({"cpu_ratio": .5}, sample(cpu=True), sample(cpu=float("inf")), sample(sensor="x"*257)):
            with self.assertRaises(ValueError):
                validate_sample("system", value)

    def test_sensitive_context_is_excluded_from_model_prompt(self):
        m = Model(); m.accept("system", sample(), 1)
        m.accept("media", dict(status="playing", player="secret-player", title="private title", artist="private artist"), 2)
        context = json.dumps(evidence(m.snapshot()))
        self.assertNotIn("private", context)
        self.assertNotIn("coretemp", context)
        self.assertIn("cpu_ratio", context)


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.model = Model(clock=lambda: self.now, wall=lambda: 1000+self.now)

    def observe(self, cpu=.95, **kwargs):
        return self.model.accept("system", sample(cpu=cpu, **kwargs), int(self.now)+1)

    def advance(self, until, **kwargs):
        events = []
        while self.now < until:
            self.now += 2
            events += self.observe(**kwargs)
        return events

    def test_dwell_hysteresis_dedup_and_recovery(self):
        self.assertEqual(self.observe(), [])
        self.assertEqual(self.advance(10), [])
        events = self.advance(12)
        self.assertEqual([x['status'] for x in events], ['active'])
        ident = events[0]['id']
        self.assertEqual(self.advance(20), [])
        self.assertEqual(self.advance(24, cpu=.8), [])  # hysteresis band
        self.assertEqual(self.advance(30, cpu=.5), [])
        self.assertEqual(self.advance(32, cpu=.5)[0]['status'], 'resolved')
        self.assertEqual(self.model.insights[ident]['evidence']['value'], .95)

    def test_missing_samples_reset_candidate_and_never_mean_recovery(self):
        self.observe(); self.advance(10)
        self.now = 30
        self.model.expire()
        self.assertEqual(self.observe(), [])
        self.assertEqual(self.advance(40), [])
        self.advance(42)
        self.model.unavailable("system", "sensor absent")
        self.assertEqual(next(iter(self.model.insights.values()))['status'], 'unknown')
        self.assertEqual(self.model.history[0]['status'], 'unknown')

    def test_restart_cannot_restore_live_readings(self):
        self.observe(); self.advance(12)
        self.model.preferences['reduced_motion'] = True
        restored = Model(self.model.export())
        self.assertFalse(restored.fresh('system'))
        self.assertEqual(restored.snapshot()['presence'], 'unknown')
        self.assertTrue(restored.preferences['reduced_motion'])
        self.assertEqual(restored.snapshot()['insights'][0]['status'], 'unknown')

    def test_disappearing_mount_stays_unknown_and_sensor_identity_isolated(self):
        self.model.accept('storage', {'mounts':[dict(path='/data',available=5,total=100,ratio=.05)]}, 1)
        self.model.accept('storage', {'mounts':[]}, 2)
        self.assertEqual(self.model.snapshot()['insights'][0]['status'], 'unknown')
        self.observe(cpu=.1, temperature=90, sensor='one')
        self.now=2; self.observe(cpu=.1, temperature=90, sensor='two')
        self.now=4; self.observe(cpu=.1, temperature=90, sensor='one')
        self.assertFalse(any(x['kind']=='thermal' and x['status']=='active' for x in self.model.insights.values()))

    def test_animation_finishes_end_before_starting_new_mode(self):
        a = Animation(clock=lambda: self.now)
        a.select('media'); self.assertEqual(a.frame(), (1,0))
        self.now=2; self.assertEqual(a.frame()[0],2)
        a.select('busy'); self.assertEqual(a.frame()[0],3)
        self.now=4; self.assertEqual(a.frame()[0],4)
        self.now=6; self.assertEqual(a.frame()[0],5)
        a.select('idle'); self.assertEqual(a.frame(reduced=True),(0,0))


class StoreTests(unittest.TestCase):
    def test_atomic_outbox_state_restart_and_sequence_nonreuse(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.sqlite3'
            store=Store(path); first=store.reserve(); identity=store.store_id
            store.save({'preferences':{'reduced_motion':True}}, [{'id':'x','status':'active'}])
            self.assertEqual(len(store.pending()),1)
            store.close(); store=Store(path)
            self.assertEqual(store.store_id,identity)
            self.assertGreaterEqual(store.reserve(),first+1024)
            self.assertTrue(store.load()['preferences']['reduced_motion'])
            store.db.execute("CREATE TRIGGER fail BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT, 'disk failure'); END")
            with self.assertRaises(sqlite3.Error):
                store.save({'preferences':{}}, [{'id':'new'}])
            self.assertTrue(store.load()['preferences']['reduced_motion'])
            self.assertEqual(len(store.pending()),1)
            store.delivered(store.pending()[0][0]); self.assertEqual(store.pending(),[])
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            store.close()


class LocalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'state.sqlite3')
        self.daemon=Daemon(Settings(sensors=[],notifications=False),self.store)

    async def asyncTearDown(self):
        self.daemon.assistant.close(); self.store.close(); self.temp.cleanup()

    async def request(self, method, params=None):
        return await self.daemon.request(method,params or {})

    async def test_queries_and_durable_controls(self):
        status=await self.request('status.get')
        self.assertEqual(status['release'],'0.14.0')
        self.assertEqual(status['presence'],'unknown')
        await self.request('preferences.set',{'reduced_motion':True})
        await self.request('attention.mute',{'seconds':3600})
        self.assertTrue(self.store.load()['preferences']['reduced_motion'])
        self.assertGreater(self.store.load()['preferences']['muted_until'],0)
        answer=await self.request('assistant.ask',{'question':'¿Cómo está el sistema?'})
        self.assertEqual(answer['provider'],'local_rules')
        for method,params in [('system.exec',{'command':'id'}),('preferences.set',{'avatar_visible':1}),('attention.mute',{'seconds':True})]:
            with self.assertRaises(ValueError):
                await self.request(method,params)

    async def test_persistence_failure_rejects_preference_and_recovers(self):
        with patch.object(self.store,'save',side_effect=sqlite3.OperationalError('full')):
            with self.assertRaises(ValueError):
                await self.request('preferences.set',{'reduced_motion':True})
        self.assertFalse(self.daemon.model.preferences['reduced_motion'])
        self.assertFalse((await self.request('status.get'))['durable'])
        await self.request('preferences.set',{'reduced_motion':True})
        status=await self.request('status.get')
        self.assertTrue(status['durable'])
        self.assertNotIn('persistence',status['health'])

    async def test_model_failure_falls_back_to_verified_facts(self):
        assistant=LocalAssistant('local-model:small',True)
        try:
            with patch.object(assistant,'_generate',side_effect=OSError('offline')):
                result=await assistant.ask('estado',self.daemon.snapshot())
            self.assertEqual(result['provider'],'local_rules')
            with patch.object(assistant,'_post') as post:
                assistant.model='model:cloud'
                with self.assertRaises(ValueError): assistant._generate('x',{})
                post.assert_not_called()
        finally: assistant.close()

    async def test_subprocess_timeout_and_output_bound(self):
        import sys
        with self.assertRaises(asyncio.TimeoutError):
            await sensors.command(sys.executable,'-c','import time; time.sleep(5)',timeout=.05)
        with self.assertRaises(ValueError):
            await sensors.command(sys.executable,'-c','print("x"*1000)',limit=32)


class UnixProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_socket_malformed_and_correlated_response(self):
        try:
            probe = socket.socket(socket.AF_UNIX)
        except PermissionError:
            self.skipTest("Host denies AF_UNIX; run this gate on Linux/CI")
        else:
            probe.close()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'control.sock'
            async def handler(method, params):
                if method != 'hello': raise ValueError('unknown method')
                return {'version':'cc.ipc/1'}
            server=Server(handler)
            listener=await asyncio.start_unix_server(server.connection,path=str(path),limit=65536)
            try:
                reader,writer=await asyncio.open_unix_connection(str(path))
                writer.write(b'{"version":"cc.ipc/1","version":"bad"}\n'); await writer.drain()
                self.assertIn('error',decode(await reader.readline()))
                writer.close(); await writer.wait_closed()
                self.assertEqual((await asyncio.to_thread(call,'hello',None,path))['version'],'cc.ipc/1')
                with self.assertRaises(ValueError):
                    await asyncio.to_thread(call,'system.exec',None,path)
            finally:
                listener.close(); await listener.wait_closed(); await server.close()


if __name__ == '__main__':
    unittest.main()
