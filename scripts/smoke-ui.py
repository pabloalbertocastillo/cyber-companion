#!/usr/bin/env python3
"""Exercise the actual GTK panel using clearly labeled deterministic observations."""
import argparse
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cyber_companion.ui.app import Application, Gtk, GLib, demo_snapshot

Gtk.init()
args=argparse.Namespace(demo=True,no_avatar=True,avatar_only=False,screenshot=None,quit_after_capture=False)
app=Application(args)
app.set_application_id('io.cybercompanion.Wisp.SmokeTest')
failures=[]

def check():
    try:
        assert app.snapshot['release']=='0.14.0'
        assert app.connection.get_text()=='MODO DEMO'
        app.show_page('history'); assert app.history.get_first_child()
        app.show_page('settings'); assert app.health_box.get_first_child()
        app.show_page('overview')
        item=app.snapshot['insights'][0]
        app.show_response({'text':'Explicación local de prueba. '*80,'provider':'local_rules'},None)
        assert app.response_box.get_visible()
        app.dismiss_response(); assert not app.response_box.get_visible()
        app.received(None,'Disconnected')
        assert app.snapshot is None and not app.ask_button.get_sensitive()
        assert app.metrics['cpu'].value.get_text()=='—'
        app.received(demo_snapshot(),None)
        assert app.ask_button.get_sensitive()
        assert app.atlas is not None
        assert app.wisp.signal['cpu'] == .34
        assert app.wisp.signal['network'] == 'NET OK'
        app.wisp.pointer_motion(None, 290, 80)
        assert app.wisp.look_target[0] > 0
        app.wisp.update('busy', True, demo_snapshot())
        assert app.wisp.look == [0., 0.]
        assert app.wisp.visual_scale == .96
        app.wisp.update('unknown', True)
        assert app.wisp.signal['cpu'] is None
        assert app.wisp.signal['network'] == 'NET —'
        print('PASS · GTK pages, evidence, bounded answer, discard, disconnect and reconnect',flush=True)
    except Exception as error:
        failures.append(str(error));print('FAIL',repr(error),flush=True)
    app.quit()
    return False

GLib.timeout_add(2500,check)
result=app.run([])
raise SystemExit(1 if failures else result)
