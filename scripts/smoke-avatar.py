#!/usr/bin/env python3
"""Exercise a separate demo avatar on real Wayland; never change daemon preferences."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cyber_companion.ui.app import Application, Gtk, Gdk, GLib, Layer, demo_snapshot
from cyber_companion.ui.interaction import AVATAR_WIDTH, AVATAR_HEIGHT

Gtk.init()
if not Layer or not Layer.is_supported():
    raise SystemExit('This gate requires a real Wayland layer-shell compositor.')
args = argparse.Namespace(demo=True, no_avatar=False, avatar_only=True,
                          screenshot=None, quit_after_capture=False)
app = Application(args)
app.set_application_id('io.cybercompanion.Wisp.AvatarTest')
failures = []


class Click:
    def __init__(self, button): self.button = button
    def get_current_button(self): return self.button


def check():
    try:
        assert app.overlay and app.overlay.get_mapped()
        assert Layer.get_keyboard_mode(app.overlay) == Layer.KeyboardMode.NONE
        assert Layer.get_exclusive_zone(app.overlay) == -1
        assert app.avatar.get_width() == AVATAR_WIDTH and app.avatar.get_height() == AVATAR_HEIGHT
        app.avatar_click(Click(1), 1, 160, 100)
        assert app.window.get_visible()
        app.avatar_click(Click(1), 1, 160, 100)
        assert not app.window.get_visible()
        app.avatar_click(Click(3), 1, 160, 100)
        assert app.popover.get_visible()
        app.popover.popdown()
        app.drag_begin(None, 192, 168)
        origin = app.drag_origin
        source = Layer.get_monitor(app.overlay)
        app.drag_update(None, -40, -30)
        app.drag_frame()
        pos = app.drag_position
        app.received(demo_snapshot(), None)
        assert Layer.get_margin(app.overlay, Layer.Edge.RIGHT) == origin[0], 'input surface moved during drag'
        assert Layer.get_monitor(app.overlay) == source
        assert app.avatar.drag_hidden and app.drag_previews
        assert any(win.get_visible() for win, *_ in app.drag_previews)
        captured = []
        submit = app.submit
        app.submit = lambda method, params, **kwargs: captured.append((method, params))
        app.drag_end()
        app.submit = submit
        expected = {'monitor': source.get_connector(), 'margin_x': pos[0], 'margin_y': pos[1]}
        assert captured == [('preferences.set', expected)]
        app.received(demo_snapshot(), None)
        assert Layer.get_margin(app.overlay, Layer.Edge.RIGHT) == pos[0], 'stale poll undid the drop'
        ack = demo_snapshot()
        ack['preferences'].update(expected)
        app.received(ack, None)
        assert app.pending_drag_prefs is None
        assert not app.avatar.drag_hidden and not app.drag_previews
        # Drive the same gesture across each real output with a stationary source.
        for destination, rect in app.output_layout():
            app.drag_begin(None, 192, 168)
            dx = rect.x+rect.width/2-app.drag_top_left[0]-192
            dy = rect.y+rect.height/2-app.drag_top_left[1]-168
            app.drag_update(None, dx, dy)
            app.drag_frame()
            assert app.drag_monitor == destination
            app.submit = lambda method, params, **kwargs: captured.append((method, params))
            app.drag_end()
            app.submit = submit
            assert Layer.get_monitor(app.overlay) == destination
            ack['preferences'].update(captured[-1][1])
            app.received(ack, None)
        app.drag_begin(None, 192, 168)
        app.drag_update(None, 80, 80)
        app.drag_cancel()
        assert not app.dragging and not app.avatar.drag_hidden and not app.drag_previews
        # Opacity does not alter the surface's hit area; all active controls wake it.
        app.avatar.pointer_leave()
        app.avatar.visibility.last_active = 0
        assert app.avatar.visibility.step(100, 1, reduced=True) == .08
        app.popover.popup()
        assert app.avatar.interacting
        app.popover.popdown()
        snap = demo_snapshot()
        for monitor in Gdk.Display.get_default().get_monitors():
            snap['preferences']['monitor'] = monitor.get_connector()
            app.received(snap, None)
            assert Layer.get_monitor(app.overlay) == monitor
        snap['preferences']['monitor'] = snap['domains']['desktop']['value']['monitor']
        snap['domains']['desktop']['value']['fullscreen'] = True
        app.received(snap, None)
        assert not app.overlay.get_visible()
        snap['domains']['desktop']['value']['fullscreen'] = False
        snap['domains']['session']['value']['locked'] = True
        app.received(snap, None)
        assert not app.overlay.get_visible()
        snap['domains']['session']['fresh'] = False
        app.received(snap, None)
        assert not app.overlay.get_visible()
        snap['domains']['session']['fresh'] = True
        snap['domains']['session']['value']['locked'] = False
        snap['preferences']['reduced_motion'] = True
        app.received(snap, None)
        assert app.overlay.get_visible() and app.avatar.reduced
        app.received(None, 'Disconnected')
        assert not app.overlay.get_visible()
        app.received(snap, None)
        assert app.overlay.get_visible()
        print('PASS · real Wayland layer, larger geometry, no keyboard grab, click/menu handlers, stable drag source, cross-output drop, stale-poll protection, cancel, opacity, both monitors, fullscreen/lock/unknown-session visibility, reduced motion and reconnect', flush=True)
    except Exception as error:
        failures.append(repr(error))
        print('FAIL', repr(error), flush=True)
    finally:
        app.quit()
    return False


GLib.timeout_add(2500, check)
code = app.run([])
raise SystemExit(1 if failures else code)
