"""Wisp v0.14: unprivileged local observation and interaction service."""
from __future__ import annotations
import argparse
import asyncio
import copy
import fcntl
import json
import os
import signal
import sqlite3
import sys
import time
from pathlib import Path
from uuid import uuid4

from . import sensors
from .assistant import LocalAssistant, explain
from .core.events import EventV2, PrivacyClass, DeliveryClass, RetentionClass
from .core.model import LEASES, Model
from .core.store import Store
from .core.validation import number
from .ipc import Server
from .settings import Settings, runtime_dir, state_dir


class Daemon:
    def __init__(self, settings: Settings, store: Store):
        self.settings, self.store = settings, store
        self.model = Model(store.load())
        self.queue = asyncio.Queue(maxsize=64)
        self.lock = asyncio.Lock()
        self.assistant = LocalAssistant(settings.ollama_model, settings.ollama_local_only_confirmed)
        self.generation = uuid4().hex
        self.sequence = store.reserve()
        self.sequence_end = self.sequence + 1024
        self.last_checkpoint = time.monotonic()
        self.durable = True
        self.notification_ids = {}
        self.started = time.monotonic()
        self.stop = asyncio.Event()

    def snapshot(self):
        value = self.model.snapshot()
        value.update({"store_id": self.store.store_id, "generation": self.generation,
                      "durable": self.durable, "uptime_s": round(time.monotonic()-self.started),
                      "assistant": {"enabled": self.assistant.enabled, "model": self.settings.ollama_model},
                      "release": "0.14.0"})
        return value

    async def persist(self, model, changes, audit=None):
        try:
            await asyncio.to_thread(self.store.save, copy.deepcopy(model.export()), changes, audit)
            self.last_checkpoint = time.monotonic()
            self.durable = True
            self.model.health.pop("persistence", None)
            model.health.pop("persistence", None)
        except (sqlite3.Error, OSError):
            self.durable = False
            self.model.health["persistence"] = {"state": "unavailable", "message": "Historial no disponible; monitoreo en memoria"}
            raise ValueError("No pude guardar el cambio. Revisa el espacio y los permisos del directorio de estado.")

    async def reduce(self):
        while True:
            domain, value, error = await self.queue.get()
            try:
                async with self.lock:
                    candidate = copy.deepcopy(self.model)
                    if error:
                        changes = candidate.unavailable(domain, error)
                    else:
                        if self.sequence == self.sequence_end:
                            self.sequence = await asyncio.to_thread(self.store.reserve)
                            self.sequence_end = self.sequence + 1024
                        # Only registered in-process sensor handles can reach this ingress.
                        event = EventV2.create(event_type=f"{domain}.observed", source=f"sensor://{domain}/local",
                            subject="host/local", sequence=self.sequence, schema=f"cc.{domain}.observation@1",
                            data=value, privacy=PrivacyClass.SENSITIVE if domain in ("media", "desktop", "virtualization") else PrivacyClass.LOCAL_PRIVATE,
                            delivery=DeliveryClass.ORDERED, retention=RetentionClass.EPHEMERAL,
                            ttl_ms=LEASES[domain]*1000)
                        changes = candidate.accept(domain, event.as_dict()["data"], self.sequence)
                        self.sequence += 1
                    if changes or time.monotonic() - self.last_checkpoint > 5:
                        try:
                            await self.persist(candidate, changes)
                        except ValueError:
                            candidate.health["persistence"] = self.model.health["persistence"]
                    self.model = candidate
            except (sqlite3.Error, OSError):
                self.durable = False
                self.model.health["persistence"] = {"state": "unavailable", "message": "No se pudo reservar la secuencia durable"}
                self.model.unavailable(domain, "Almacenamiento no disponible")
            except ValueError:
                self.model.unavailable(domain, "Observación rechazada")
            finally:
                self.queue.task_done()

    async def sensor(self, name: str, function, interval: float, threaded=False):
        failures = 0
        while True:
            try:
                if threaded:
                    # At most one outstanding native read per adapter; no retry pile-up.
                    future = asyncio.create_task(asyncio.to_thread(function))
                    try:
                        result = await asyncio.wait_for(asyncio.shield(future), 4)
                    except asyncio.TimeoutError:
                        await self.queue.put((name, None, "Lectura lenta; esperando al sensor"))
                        result = await future
                else:
                    result = await function()
                await self.queue.put((name, result, None))
                failures = 0
            except asyncio.CancelledError:
                raise
            except (OSError, ValueError, KeyError, TypeError, asyncio.TimeoutError):
                failures += 1
                await self.queue.put((name, None, "Fuente no disponible; reintento automático"))
            await asyncio.sleep(min(30, interval * 2**min(failures, 3)))

    async def maintenance(self):
        previous = time.monotonic()
        previous_wall = time.time()
        while True:
            await asyncio.sleep(1)
            now, wall = time.monotonic(), time.time()
            async with self.lock:
                candidate = copy.deepcopy(self.model)
                # Wall/monotonic drift or missed ticks invalidate leases after resume.
                gap = now - previous > 5 or abs((wall - previous_wall) - (now - previous)) > 5
                changes = []
                if gap:
                    for domain in list(candidate.domains):
                        changes.extend(candidate.unavailable(domain, "Actualizando después de una pausa"))
                    candidate.preferences["muted_until"] = 0
                    for item in candidate.insights.values():
                        item["snoozed_until"] = 0
                changes.extend(candidate.expire())
                if changes:
                    try:
                        await self.persist(candidate, changes)
                    except ValueError:
                        candidate.health["persistence"] = self.model.health["persistence"]
                self.model = candidate
            previous, previous_wall = now, wall

    async def notifications(self):
        while True:
            await asyncio.sleep(2)
            try:
                pending = await asyncio.to_thread(self.store.pending)
                for ident, item in pending:
                    snap = self.snapshot()
                    session = snap["domains"].get("session", {})
                    unlocked = session.get("fresh") and session["value"].get("locked") is False
                    insight = next((x for x in snap["insights"] if x["id"] == item["id"]), None)
                    visible = self.settings.notifications and unlocked and item["status"] in ("active", "resolved")
                    visible &= bool(insight and insight["status"] == item["status"])
                    if item["severity"] != "critical":
                        visible &= snap["preferences"]["muted_until"] <= time.time()
                    if insight:
                        visible &= not insight["acknowledged"] and insight["snoozed_until"] <= time.time()
                    if visible:
                        title = "Wisp · " + ("Recuperación" if item["status"] == "resolved" else "Observación")
                        args = ["notify-send", "--app-name=Wisp", "--print-id", "--expire-time=8000"]
                        if item["id"] in self.notification_ids:
                            args += ["--replace-id", self.notification_ids[item["id"]]]
                        try:
                            result = (await sensors.command(*args, title, item["title"], limit=128)).strip()
                            if result.isdigit():
                                self.notification_ids[item["id"]] = result
                        except (OSError, ValueError, asyncio.TimeoutError):
                            self.model.health["notifications"] = {"state": "unavailable", "message": "Consulta las observaciones en el panel"}
                    # Suppressed/unavailable notifications remain inspectable as insights.
                    await asyncio.to_thread(self.store.delivered, ident)
            except (sqlite3.Error, OSError):
                await asyncio.sleep(3)

    async def request(self, method: str, params: dict):
        if method == "daemon.stop":
            if params:
                raise ValueError("unexpected parameters")
            self.stop.set()
            return {"ok": True}
        if method in ("hello", "status.get", "health.get", "insights.list"):
            if params:
                raise ValueError("unexpected parameters")
            if method == "hello":
                return {"version": "cc.ipc/1", "release": "0.14.0", "methods": ["status.get", "health.get", "insights.list", "insight.explain", "insight.acknowledge", "insight.snooze", "attention.mute", "preferences.set", "assistant.ask", "daemon.stop"]}
            return self.snapshot() if method == "status.get" else self.snapshot()["health" if method == "health.get" else "insights"]
        if method == "insight.explain":
            if set(params) != {"id"} or type(params["id"]) is not str:
                raise ValueError("invalid insight ID")
            return {"text": explain(self.snapshot(), params["id"]), "provider": "local_rules"}
        if method == "assistant.ask":
            if set(params) != {"question"} or type(params["question"]) is not str or not 1 <= len(params["question"].strip()) <= 1000:
                raise ValueError("Escribe una pregunta de hasta 1,000 caracteres.")
            if not self.durable:
                return {"text": explain(self.snapshot()), "provider": "local_rules", "note": "Historial no disponible"}
            return await self.assistant.ask(params["question"], self.snapshot())
        async with self.lock:
            candidate = copy.deepcopy(self.model)
            if method in ("insight.acknowledge", "insight.snooze"):
                expected = {"id", "seconds"} if method.endswith("snooze") else {"id"}
                if set(params) != expected or type(params["id"]) is not str or params["id"] not in candidate.insights:
                    raise ValueError("invalid insight request")
                item = candidate.insights[params["id"]]
                if method.endswith("snooze"):
                    if type(params["seconds"]) is not int or not 0 <= params["seconds"] <= 86400:
                        raise ValueError("invalid snooze duration")
                    item["snoozed_until"] = time.time() + params["seconds"]
                else:
                    item["acknowledged"] = True
            elif method == "attention.mute":
                if set(params) != {"seconds"} or type(params["seconds"]) is not int or not 0 <= params["seconds"] <= 86400:
                    raise ValueError("invalid mute duration")
                candidate.preferences["muted_until"] = time.time() + params["seconds"]
            elif method == "preferences.set":
                if not params or set(params) - {"reduced_motion", "avatar_visible", "monitor", "margin_x", "margin_y"}:
                    raise ValueError("unknown preference")
                for key, value in params.items():
                    if key in ("reduced_motion", "avatar_visible") and type(value) is not bool:
                        raise ValueError("invalid boolean preference")
                    if key == "monitor" and (type(value) is not str or len(value) > 128):
                        raise ValueError("invalid monitor")
                    if key.startswith("margin_") and (type(value) is not int or not 0 <= value <= 32768):
                        raise ValueError("invalid margin")
                candidate.preferences.update(params)
            else:
                raise ValueError("unknown or unavailable method")
            candidate.revision += 1
            await self.persist(candidate, [], {"method": method, "params": params})
            self.model = candidate
            return {"ok": True}

    async def run(self, path: Path):
        server = Server(self.request)
        listener = await asyncio.start_unix_server(server.connection, path=str(path), limit=65536)
        path.chmod(0o600)
        linux = sensors.Linux()
        catalog = {"system": (linux.sample, 2, True), "storage": (lambda: sensors.storage(self.settings.storage_paths), 30, True),
                   "network": (sensors.network, 5, True), "media": (sensors.media, 5, False),
                   "desktop": (sensors.desktop, 2, False), "session": (sensors.session, 2, False),
                   "virtualization": (sensors.virtualization, 10, False)}
        jobs = [asyncio.create_task(self.reduce()), asyncio.create_task(self.maintenance()), asyncio.create_task(self.notifications())]
        jobs += [asyncio.create_task(self.sensor(name, *catalog[name])) for name in self.settings.sensors]
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stop.set)
        print(f"Wisp 0.14 listo · {path}", flush=True)
        try:
            await self.stop.wait()
        finally:
            listener.close()
            await listener.wait_closed()
            await server.close()
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
            try:
                await self.persist(self.model, [])
            except ValueError:
                pass
            self.assistant.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        settings = Settings.load(args.config)
        directory = runtime_dir()
        lock_path = directory / "daemon.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("Wisp ya está ejecutándose en esta sesión.")
            path = directory / "control.sock"
            if path.exists():
                path.unlink()  # Exclusive daemon ownership established before cleanup.
            store = Store(state_dir() / "companion.sqlite3")
            try:
                asyncio.run(Daemon(settings, store).run(path))
            finally:
                path.unlink(missing_ok=True)
                store.close()
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"Wisp: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
