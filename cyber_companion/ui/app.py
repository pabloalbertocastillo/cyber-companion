"""Wisp native console and optional Wayland avatar, both clients of the daemon."""
from __future__ import annotations
import argparse
import concurrent.futures
import os
import math
import time
from pathlib import Path

# Layer shell must interpose before GTK loads libwayland-client (upstream Python contract).
_layer_library = None
if os.environ.get("WAYLAND_DISPLAY"):
    try:
        from ctypes import CDLL, RTLD_GLOBAL
        from ctypes.util import find_library
        _layer_library = CDLL(find_library("gtk4-layer-shell") or "libgtk4-layer-shell.so.0", mode=RTLD_GLOBAL)
    except OSError:
        pass

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gdk, GLib, Gio, Pango
    import cairo
except (ImportError, ValueError) as error:
    raise SystemExit("Wisp requiere GTK4, PyGObject y Pycairo. Consulta docs/DESKTOP_V014.md.") from error

Layer = None
if _layer_library is not None:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as Layer
    except (ImportError, ValueError):
        pass

from ..ipc import call
from ..core.model import Model
from ..assistant import explain
from .animation import Animation
from .hologram import telemetry, anatomy_scale, paint_entity
from .interaction import (AVATAR_WIDTH, AVATAR_HEIGHT, Output, drag_placement,
                          AMBIENT_OPACITY, AmbientVisibility, companion_monitor)

ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / "assets/sprites/companion-wisp-system-v0.12.png"


def label(text="", css="", wrap=False):
    item = Gtk.Label(label=text, xalign=0)
    for name in css.split():
        item.add_css_class(name)
    if wrap:
        item.set_wrap(True)
        item.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return item


def box(vertical=True, spacing=0, css=""):
    item = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL, spacing=spacing)
    if css:
        item.add_css_class(css)
    return item


def margins(widget, value):
    for edge in ("top", "bottom", "start", "end"):
        getattr(widget, "set_margin_" + edge)(value)


def button(text, callback, css=""):
    item = Gtk.Button(label=text)
    for name in css.split():
        item.add_css_class(name)
    item.connect("clicked", callback)
    return item


def clear(container):
    child = container.get_first_child()
    while child:
        following = child.get_next_sibling()
        container.remove(child)
        child = following


class Sparkline(Gtk.DrawingArea):
    def __init__(self, color=(.4, .86, .76)):
        super().__init__()
        self.color = color
        self.samples = []
        self.set_content_height(27)
        self.set_draw_func(self.draw)

    def update(self, value):
        self.samples = (self.samples + [value])[-48:]
        self.queue_draw()

    def draw(self, area, cr, width, height):
        cr.set_source_rgba(*self.color, .12)
        cr.set_line_width(1)
        cr.move_to(0, height-1)
        cr.line_to(width, height-1)
        cr.stroke()
        if len(self.samples) < 2:
            return
        cr.set_source_rgba(*self.color, .9)
        cr.set_line_width(1.6)
        drawing = False
        for i, v in enumerate(self.samples):
            if v is None:
                cr.stroke()
                drawing = False
                continue
            x, y = i/(len(self.samples)-1)*width, height-3-max(0, min(1, v))*(height-6)
            (cr.line_to if drawing else cr.move_to)(x, y)
            drawing = True
        cr.stroke()


class Metric(Gtk.Box):
    def __init__(self, title, subtitle, color):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.add_css_class("metric")
        self.set_hexpand(True)
        self.append(label(title, "overline"))
        row = box(False, 9)
        self.value, self.unit = label("—", "metric-value"), label(subtitle, "metric-unit")
        self.unit.set_valign(Gtk.Align.END)
        self.unit.set_margin_bottom(5)
        row.append(self.value)
        row.append(self.unit)
        self.append(row)
        self.chart = Sparkline(color)
        self.append(self.chart)

    def update(self, value, text, subtitle=None):
        self.value.set_text(text)
        if subtitle is not None:
            self.unit.set_text(subtitle)
        self.chart.update(value)


class Wisp(Gtk.DrawingArea):
    def __init__(self, atlas, hero=False):
        super().__init__()
        self.atlas, self.hero = atlas, hero
        self.animation = Animation()
        self.presence = "idle"
        self.reduced = False
        self.last_tick = 0
        self.last_frame = 0
        self.visibility = AmbientVisibility(time.monotonic())
        self.interacting = False
        self.drag_hidden = False
        self.pose_locked = False
        self.signal = telemetry(None)
        self.hovered = False
        self.visual_scale = .96
        self.look = [0., 0.]
        self.look_target = [0., 0.]
        self.set_content_width(294 if hero else AVATAR_WIDTH)
        self.set_content_height(280 if hero else AVATAR_HEIGHT)
        self.set_draw_func(self.draw)
        self.add_tick_callback(self.tick)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self.pointer_enter)
        motion.connect("leave", self.pointer_leave)
        motion.connect("motion", self.pointer_motion)
        self.add_controller(motion)
        self.set_cursor_from_name("grab" if not hero else "pointer")

    def pointer_enter(self, *_):
        self.hovered = True
        self.queue_draw()

    def pointer_leave(self, *_):
        self.hovered = False
        self.look_target = [0., 0.]
        self.queue_draw()

    def pointer_motion(self, controller, x, y):
        self.look_target = [max(-1.,min(1.,(x-self.get_width()/2)/100)),
                            max(-1.,min(1.,(y-self.get_height()/2)/100))]

    def tick(self, widget, frame_clock):
        now = frame_clock.get_frame_time()
        dt = min(.1, (now-self.last_frame)/1_000_000) if self.last_frame else 1/60
        self.last_frame = now
        active = self.hero or self.hovered or self.interacting
        previous = self.visibility.opacity
        self.visibility.step(time.monotonic(), dt, active, self.reduced)
        if self.visibility.opacity != previous:
            self.queue_draw()
        interval = 16000 if active else (125000 if self.visibility.opacity <= AMBIENT_OPACITY + .002 else 42000)
        if not self.reduced and self.get_mapped() and now - self.last_tick >= interval:
            # Gentle interpolation keeps changes in load and pointer position fluid.
            elapsed = min(.1, (now-self.last_tick)/1_000_000)
            weight = 1-math.exp(-elapsed/ .25)
            if not self.pose_locked:
                self.visual_scale += (anatomy_scale(self.signal,self.hovered)-self.visual_scale)*weight
                self.look = [a+(b-a)*weight for a,b in zip(self.look,self.look_target)]
            self.last_tick = now
            self.queue_draw()
        return True

    def update(self, presence, reduced, snapshot=None):
        self.presence, self.reduced = presence, reduced
        self.animation.select(presence)
        self.signal = telemetry(snapshot)
        if reduced:
            self.visual_scale = anatomy_scale(self.signal,reduced=True)
            self.look = [0.,0.]
        mount = self.signal["storage"]
        detail = f"\n{mount['path']}: {mount['available']/1024**3:.1f} GiB libres" if mount else ""
        cpu = self.signal["cpu"]
        memory = self.signal["memory"]
        cpu_text = "sin lectura" if cpu is None else f"{cpu:.0%}"
        memory_text = "sin lectura" if memory is None else f"{memory:.0%}"
        vms = self.signal["running_vms"]
        route = self.signal["route"]
        route_text = "disponible" if route is True else "sin ruta" if route is False else "sin lectura"
        self.set_tooltip_text(
            "Clic para abrir · Arrastra entre pantallas · Clic derecho para opciones"
            f"\nNúcleo y venas: CPU {cpu_text} · Branquias del manto: memoria {memory_text}"
            f"\nCuernos: ruta local {route_text} · Máscara: escritorio {self.signal['workspace']}"
            f"\nVértebras: {vms if vms is not None else 'sin lectura de'} VM activas"
            "\nFilamentos violetas: multimedia · Núcleo ámbar: temperatura cerca del límite" + detail)
        self.queue_draw()

    def draw(self, area, cr, width, height):
        if self.drag_hidden:
            return
        seconds = 0 if self.reduced else time.monotonic()
        cr.push_group()
        if self.atlas:
            row, frame = self.animation.frame(self.reduced)
            paint_entity(cr,self.atlas,row,frame,width,height,self.signal,seconds,
                         self.visual_scale,self.look,self.reduced,self.presence)
        cr.pop_group_to_source()
        cr.paint_with_alpha(1. if self.hero else self.visibility.opacity)


def demo_snapshot():
    clock = [0.0]
    model = Model(clock=lambda: clock[0])
    values = {"cpu_ratio": .34, "memory_ratio": .58, "temperature_c": 62,
              "temperature_limit_c": 85, "sensor": "CPU / Package", "psi_cpu": 1.2, "psi_memory": 0., "psi_io": .2}
    model.accept("system", values, 1)
    model.accept("storage", {"mounts": [{"path": "/", "available": 18*1024**3, "total": 256*1024**3, "ratio": .07}]}, 2)
    model.accept("network", {"interfaces": ["ethernet"], "default_route": True}, 3)
    model.accept("media", {"status": "playing", "player": "music", "title": "Night Drive", "artist": "Sesión nocturna"}, 4)
    model.accept("desktop", {"monitor": "DP-2", "workspace": "3", "fullscreen": False, "outputs": ["DP-2", "DP-1"]}, 5)
    model.accept("session", {"locked": False}, 6)
    snap = model.snapshot()
    snap.update({"release": "0.14.0", "durable": True, "uptime_s": 1240, "assistant": {"enabled": False, "model": ""}})
    return snap


class Application(Gtk.Application):
    def __init__(self, args):
        super().__init__(application_id="io.cybercompanion.Wisp", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.args = args
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="wisp-client")
        self.snapshot = None
        self.polling = False
        self.is_asking = False
        self.closed = False
        self.updating = False
        self.issue_signature = None
        self.history_signature = None
        self.health_signature = None
        self.answer_generation = 0
        self.atlas = None
        self.overlay = None
        self.drag_previews = []
        self.pending_drag_prefs = None
        self.window = None
        self.explicit_open = not args.avatar_only
        self.monitor_options = [""]
        self.pending_tasks = set()
        self.connect("activate", self.activate)
        self.connect("shutdown", self.shutdown)

    def submit(self, method, params=None, callback=None):
        if self.args.demo:
            if method == "status.get":
                GLib.idle_add(callback, demo_snapshot(), None)
            elif method in ("insight.explain", "assistant.ask"):
                GLib.idle_add(callback or self.show_response, {"text": explain(self.snapshot, (params or {}).get("id", "")), "provider": "local_rules", "note": "Demostración"}, None)
            else:
                self.note.set_text("Modo demostración · los controles no modifican tu sistema")
            return
        future = self.pool.submit(call, method, params, timeout=45 if method == "assistant.ask" else 3)
        self.pending_tasks.add(future)
        def complete(f):
            self.pending_tasks.discard(f)
            try:
                value, error = f.result(), None
            except (OSError, ValueError) as exc:
                value, error = None, str(exc)
            if not self.closed:
                GLib.idle_add(callback or self.command_done, value, error)
        future.add_done_callback(complete)

    def activate(self, *_):
        if self.window:
            self.open_panel()
            return
        provider = Gtk.CssProvider()
        provider.load_from_path(str(Path(__file__).with_name("theme.css")))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        if ATLAS.exists():
            self.atlas = cairo.ImageSurface.create_from_png(str(ATLAS))
        self.build_panel()
        self.build_overlay()
        if not self.args.avatar_only or not self.overlay:
            self.open_panel()
        self.poll()
        GLib.timeout_add(1500, self.poll)
        if self.args.screenshot:
            GLib.timeout_add(2500, self.capture)

    def build_panel(self):
        self.window = Gtk.ApplicationWindow(application=self, title="Cyber Companion")
        self.window.add_css_class("wisp-panel")
        self.window.set_default_size(1060, 840)
        self.window.connect("close-request", self.close_panel)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self.key)
        self.window.add_controller(key)
        root = box(True, 20)
        margins(root, 26)
        self.window.set_child(root)
        header = box(False, 12)
        header.append(label("◈", "brand-mark"))
        brand = box(True, 2)
        brand.append(label("Cyber Companion", "brand"))
        header.append(brand)
        spacer = box(); spacer.set_hexpand(True); header.append(spacer)
        self.connection = label("CONECTANDO", "connection")
        self.connection.set_valign(Gtk.Align.CENTER)
        header.append(self.connection)
        header.append(button("Cerrar", lambda _: self.close_panel(), "flat"))
        root.append(header)
        body = box(False, 22); body.set_vexpand(True)
        root.append(body)
        hero = box(True, 0, "hero"); hero.set_size_request(300, -1)
        hero.set_hexpand(False)
        hero_scroll = Gtk.ScrolledWindow()
        hero_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        hero_scroll.set_min_content_width(322)
        hero_scroll.set_max_content_width(322)
        hero_scroll.set_child(hero)
        body.append(hero_scroll)
        hero_top = box(True, 8); margins(hero_top, 22)
        hero_top.append(label("P R E S E N C I A   L O C A L", "overline"))
        hero_top.append(label("Una mirada a tu sistema.", "hero-subtitle"))
        hero.append(hero_top)
        self.wisp = Wisp(self.atlas, hero=True)
        hero.append(self.wisp)
        hero_bottom = box(True, 14); margins(hero_bottom, 22)
        self.hero_title = label("Estoy aquí.", "hero-title", True)
        self.hero_subtitle = label("Esperando lecturas recientes.", "hero-subtitle", True)
        self.hero_title.set_max_width_chars(22)
        self.hero_subtitle.set_max_width_chars(28)
        hero_bottom.append(self.hero_title); hero_bottom.append(self.hero_subtitle)
        hero_bottom.append(Gtk.Separator())
        self.media_label = label("◌  Sin reproducción", "muted", True)
        self.media_label.set_max_width_chars(28)
        hero_bottom.append(self.media_label)
        self.desktop_label = label("ESCRITORIO  /  —", "overline")
        hero_bottom.append(self.desktop_label)
        space = box(); space.set_vexpand(True); hero_bottom.append(space)
        self.mute_button = button("Silenciar avisos · 1 h", self.mute)
        self.mute_button.set_tooltip_text("Silencia avisos ordinarios. Los térmicos críticos conservan su aviso; puedes revisarlos o posponerlos individualmente.")
        hero_bottom.append(self.mute_button)
        motion_row = box(False, 12)
        motion_text = label("Movimiento reducido", "muted"); motion_text.set_hexpand(True)
        motion_row.append(motion_text)
        self.motion = Gtk.Switch(); self.motion.set_valign(Gtk.Align.CENTER)
        self.motion.connect("notify::active", self.motion_changed)
        motion_row.append(self.motion); hero_bottom.append(motion_row)
        hero_bottom.set_vexpand(True); hero.append(hero_bottom)
        right = box(True, 17); right.set_hexpand(True); body.append(right)
        tabs = box(False, 5); self.tabs = {}
        for key, text in (("overview", "Vista general"), ("history", "Actividad"), ("settings", "Conexiones")):
            control = button(text, lambda _, name=key: self.show_page(name), "tab")
            self.tabs[key] = control; tabs.append(control)
        right.append(tabs)
        self.stack = Gtk.Stack(); self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(180); self.stack.set_vexpand(True)
        self.stack.set_vhomogeneous(False)
        right.append(self.stack)
        overview = box(True, 17)
        metrics = Gtk.Grid(column_spacing=12, row_spacing=12)
        self.metrics = {}
        colors = ((.39,.87,.77),(.62,.57,.9),(.86,.71,.47),(.37,.71,.89))
        for i, (key, title, unit) in enumerate((("cpu", "CPU", "en uso"), ("memory", "MEMORIA", "en uso"), ("temperature", "TEMPERATURA", "sensor"), ("storage", "ALMACENAMIENTO", "disponible"))):
            metric = Metric(title, unit, colors[i]); self.metrics[key] = metric
            metrics.attach(metric, i%2, i//2, 1, 1)
        overview.append(metrics)
        heading = box(False, 8)
        heading.append(label("Tu sistema, en contexto", "section-title"))
        gap = box(); gap.set_hexpand(True); heading.append(gap)
        self.count = label("—", "section-count"); heading.append(self.count)
        overview.append(heading)
        self.issues = box(True, 8)
        issue_scroll = Gtk.ScrolledWindow(); issue_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        issue_scroll.set_min_content_height(130); issue_scroll.set_vexpand(True); issue_scroll.set_child(self.issues)
        overview.append(issue_scroll)
        self.stack.add_named(overview, "overview")
        history_scroll = Gtk.ScrolledWindow(); history_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.history = box(True, 10); history_scroll.set_child(self.history); self.stack.add_named(history_scroll, "history")
        settings = box(True, 16)
        settings.append(label("Conexiones del compañero", "section-title"))
        settings.append(label("Cada fuente funciona de forma independiente. Si falta una, Wisp conserva las demás.", "muted", True))
        self.health_box = box(True, 12); settings.append(self.health_box)
        settings.append(Gtk.Separator())
        settings.append(label("MONITOR DEL AVATAR", "overline"))
        self.monitors = Gtk.DropDown.new_from_strings(["Automático · pantalla sin foco"])
        self.monitors.connect("notify::selected", self.monitor_changed)
        settings.append(self.monitors)
        self.avatar_toggle = Gtk.CheckButton(label="Mostrar avatar en el escritorio")
        self.avatar_toggle.connect("toggled", self.avatar_changed); settings.append(self.avatar_toggle)
        self.ai_info = label("", "muted", True); settings.append(self.ai_info)
        settings.append(label("Los modelos son opcionales. Las observaciones y sus explicaciones básicas funcionan localmente.", "muted", True))
        settings_scroll = Gtk.ScrolledWindow()
        settings_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        settings_scroll.set_child(settings)
        self.stack.add_named(settings_scroll, "settings")
        self.response_box = box(True, 6, "detail")
        self.response_title = label("LECTURAS VERIFICADAS", "overline")
        self.response_text = label("", "answer", True); self.response_text.set_selectable(True)
        response_header = box(False, 8)
        self.response_title.set_hexpand(True); response_header.append(self.response_title)
        self.dismiss_button = button("Descartar", self.dismiss_response, "mini flat")
        response_header.append(self.dismiss_button)
        self.response_box.append(response_header)
        response_scroll = Gtk.ScrolledWindow()
        response_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        response_scroll.set_max_content_height(135)
        response_scroll.set_propagate_natural_height(True)
        response_scroll.set_child(self.response_text)
        self.response_box.append(response_scroll)
        self.response_box.set_visible(False); right.append(self.response_box)
        composer = box(False, 8, "composer")
        self.question = Gtk.Entry(placeholder_text="Pregúntame por tu sistema…")
        self.question.set_hexpand(True); self.question.set_max_length(1000)
        self.question.connect("activate", self.ask)
        composer.append(self.question)
        self.ask_button = button("Consultar ↗", self.ask, "primary"); composer.append(self.ask_button)
        right.append(composer)
        self.note = label("Procesamiento local · Sin acciones automáticas sobre tu sistema", "footer", True)
        root.append(self.note)
        self.show_page("overview")

    def build_overlay(self):
        if not Layer or not Layer.is_supported() or self.args.no_avatar:
            return
        self.overlay = Gtk.ApplicationWindow(application=self)
        self.overlay.add_css_class("wisp-avatar")
        self.overlay.set_decorated(False)
        Layer.init_for_window(self.overlay)
        Layer.set_namespace(self.overlay, "cyber-companion-wisp")
        Layer.set_layer(self.overlay, Layer.Layer.TOP)
        Layer.set_anchor(self.overlay, Layer.Edge.RIGHT, True)
        Layer.set_anchor(self.overlay, Layer.Edge.BOTTOM, True)
        # Absolute monitor margins must include panels' reserved areas.
        Layer.set_exclusive_zone(self.overlay, -1)
        Layer.set_keyboard_mode(self.overlay, Layer.KeyboardMode.NONE)
        self.avatar = Wisp(self.atlas)
        self.overlay.set_child(self.avatar)
        self.overlay.connect("realize", self.input_region)
        self.avatar.connect("resize", lambda *_: self.input_region())
        click = Gtk.GestureClick(); click.set_button(0)
        click.connect("pressed", lambda *_: setattr(self, "dragged", False))
        click.connect("released", self.avatar_click); self.avatar.add_controller(click)
        drag = Gtk.GestureDrag(); drag.connect("drag-begin", self.drag_begin)
        drag.connect("drag-update", self.drag_update); drag.connect("drag-end", self.drag_end)
        drag.connect("cancel", self.drag_cancel)
        self.avatar.add_controller(drag)
        click.group(drag)
        self.avatar.add_tick_callback(self.drag_frame)
        self.dragged = False
        self.dragging = False
        self.drag_origin = (32, 24)
        self.drag_position = self.drag_origin
        menu = box(True, 6)
        menu.append(button("Abrir Cyber Companion", lambda _: self.open_panel(), "flat"))
        menu.append(button("Silenciar · 1 h", self.mute, "flat"))
        menu.append(button("Reducir / activar movimiento", lambda _: self.submit("preferences.set", {"reduced_motion": not (self.snapshot or {}).get("preferences", {}).get("reduced_motion", False)}), "flat"))
        menu.append(button("Ocultar avatar", lambda _: self.submit("preferences.set", {"avatar_visible": False}), "flat"))
        menu.append(button("Salir de la interfaz", lambda _: self.quit(), "flat"))
        self.popover = Gtk.Popover(); self.popover.set_child(menu); self.popover.set_parent(self.avatar)
        self.popover.connect("notify::visible", lambda *_: self.avatar_activity())
        self.window.connect("notify::visible", lambda *_: self.avatar_activity())

    def avatar_activity(self):
        self.avatar.interacting = (self.dragging or self.popover.get_visible()
                                   or self.window.get_visible())

    def input_region(self, *_):
        if self.overlay and self.overlay.get_surface():
            width, height = self.avatar.get_width(), self.avatar.get_height()
            region = cairo.Region(cairo.RectangleInt(int(width*.22), int(height*.12), int(width*.56), int(height*.79)))
            self.overlay.get_surface().set_input_region(region)

    def avatar_click(self, gesture, count, x, y):
        if self.dragged:
            return
        if gesture.get_current_button() == 3:
            self.popover.popup()
        elif gesture.get_current_button() == 1:
            if self.window.get_visible():
                self.close_panel()
            else:
                self.open_panel()

    def output_layout(self):
        monitors = Gdk.Display.get_default().get_monitors()
        result = []
        for monitor in monitors:
            rect = monitor.get_geometry()
            result.append((monitor, Output(monitor.get_connector(), rect.x, rect.y,
                                           rect.width, rect.height)))
        return result

    def drag_begin(self, gesture=None, x=0, y=0):
        self.dragged = False
        self.dragging = True
        self.drag_delta = (0., 0.)
        self.drag_applied = None
        self.drag_hotspot = (x, y)
        self.drag_monitor = (Layer.get_monitor(self.overlay) or
            Gdk.Display.get_default().get_monitor_at_surface(self.overlay.get_surface()))
        if self.drag_monitor is None:
            self.dragging = False
            return
        rect = self.drag_monitor.get_geometry()
        self.drag_origin = (Layer.get_margin(self.overlay, Layer.Edge.RIGHT),
                            Layer.get_margin(self.overlay, Layer.Edge.BOTTOM))
        self.drag_position = self.drag_origin
        self.drag_size = (self.avatar.get_width(), self.avatar.get_height())
        self.drag_top_left = (rect.x+rect.width-self.drag_size[0]-self.drag_origin[0],
                              rect.y+rect.height-self.drag_size[1]-self.drag_origin[1])
        self.avatar_activity()

    def build_drag_previews(self):
        # Keep the input surface stationary until release: moving/remapping it
        # feeds its own motion back into GestureDrag and can lose Wayland's grab.
        # Only these input-transparent visual copies cross output boundaries.
        for monitor, output in self.output_layout():
            window = Gtk.ApplicationWindow(application=self)
            window.add_css_class("wisp-avatar")
            window.set_decorated(False)
            Layer.init_for_window(window)
            Layer.set_namespace(window, "cyber-companion-drag")
            Layer.set_layer(window, Layer.Layer.OVERLAY)
            Layer.set_anchor(window, Layer.Edge.RIGHT, True)
            Layer.set_anchor(window, Layer.Edge.BOTTOM, True)
            Layer.set_exclusive_zone(window, -1)
            Layer.set_keyboard_mode(window, Layer.KeyboardMode.NONE)
            Layer.set_monitor(window, monitor)
            preview = Wisp(self.atlas)
            preview.animation = self.avatar.animation
            preview.update(self.avatar.presence, self.avatar.reduced, self.snapshot)
            preview.visual_scale = self.avatar.visual_scale
            preview.look = self.avatar.look[:]
            preview.pose_locked = True
            preview.interacting = True
            window.set_child(preview)
            window.connect("realize", lambda win: win.get_surface().set_input_region(cairo.Region()))
            self.drag_previews.append((window, preview, monitor, output))
        self.avatar.drag_hidden = True
        self.avatar.pose_locked = True
        self.avatar.queue_draw()
        self.avatar.set_cursor_from_name("grabbing")

    def drag_update(self, gesture, dx, dy):
        if not self.dragging:
            return
        if not self.dragged and dx*dx+dy*dy < 36:
            return
        if not self.dragged:
            self.dragged = True
            self.build_drag_previews()
        self.drag_delta = (dx, dy)

    def drag_frame(self, *_):
        if not self.dragging or not self.dragged or self.drag_delta == self.drag_applied:
            return True
        self.drag_applied = self.drag_delta
        left = self.drag_top_left[0]+self.drag_delta[0]
        top = self.drag_top_left[1]+self.drag_delta[1]
        width, height = self.drag_size
        pointer = (left+self.drag_hotspot[0], top+self.drag_hotspot[1])
        layout = self.output_layout()
        placement = drag_placement([o for _, o in layout], pointer, self.drag_hotspot, self.drag_size)
        if placement is None:
            self.drag_cancel()
            return True
        name, mx, my = placement
        self.drag_monitor = next(m for m, o in layout if o.name == name)
        self.drag_position = (mx, my)
        for window, preview, monitor, output in self.drag_previews:
            intersects = (monitor.is_valid() and left < output.x+output.width and
                left+width > output.x and top < output.y+output.height and top+height > output.y)
            if intersects:
                Layer.set_margin(window, Layer.Edge.RIGHT, round(output.x+output.width-left-width))
                Layer.set_margin(window, Layer.Edge.BOTTOM, round(output.y+output.height-top-height))
            window.set_visible(intersects)
        return True

    def finish_drag_visuals(self):
        self.dragging = False
        self.avatar.drag_hidden = False
        self.avatar.pose_locked = False
        self.avatar.set_cursor_from_name("grab")
        self.avatar.visibility.last_active = time.monotonic()
        self.avatar.queue_draw()
        for window, *_ in self.drag_previews:
            window.destroy()
        self.drag_previews.clear()
        self.avatar_activity()

    def drag_end(self, gesture=None, dx=None, dy=None):
        if not self.dragging:
            return
        if dx is not None and dy is not None:
            self.drag_update(gesture, dx, dy)
        self.drag_frame()
        if not self.dragging:
            return
        # Remapping the released source can synchronously cancel its old gesture.
        self.dragging = False
        if self.dragged and self.drag_monitor.is_valid():
            prefs = {"monitor": self.drag_monitor.get_connector(),
                     "margin_x": self.drag_position[0], "margin_y": self.drag_position[1]}
            self.pending_drag_prefs = prefs
            Layer.set_monitor(self.overlay, self.drag_monitor)
            Layer.set_margin(self.overlay, Layer.Edge.RIGHT, prefs["margin_x"])
            Layer.set_margin(self.overlay, Layer.Edge.BOTTOM, prefs["margin_y"])
            def saved(value, error):
                if error and self.pending_drag_prefs is prefs:
                    self.pending_drag_prefs = None
                return self.command_done(value, error)
            self.submit("preferences.set", prefs, callback=saved)
        self.finish_drag_visuals()

    def drag_cancel(self, *_):
        if self.dragging:
            self.finish_drag_visuals()

    def show_page(self, name):
        self.stack.set_visible_child_name(name)
        for key, tab in self.tabs.items():
            (tab.add_css_class if key == name else tab.remove_css_class)("selected")

    def open_panel(self):
        self.explicit_open = True
        self.window.present()
        self.poll()

    def close_panel(self, *_):
        if self.overlay:
            self.window.set_visible(False)
            self.explicit_open = False
        else:
            self.quit()
        return True

    def key(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close_panel()
            return True
        return False

    def poll(self):
        if not self.polling and not self.closed:
            self.polling = True
            self.submit("status.get", callback=self.received)
        return not self.closed

    def received(self, value, error):
        self.polling = False
        if error:
            self.snapshot = None
            self.issue_signature = None
            self.answer_generation += 1
            self.response_box.set_visible(False)
            clear(self.issues)
            self.issues.append(label("Las observaciones reaparecerán al reconectar.", "muted", True))
            self.media_label.set_text("◌  Sin lectura reciente")
            self.desktop_label.set_text("ESCRITORIO  /  —")
            self.count.set_text("SIN CONEXIÓN")
            for control in (self.motion, self.mute_button, self.avatar_toggle, self.monitors):
                control.set_sensitive(False)
            self.connection.set_text("SIN CONEXIÓN")
            self.connection.add_css_class("offline")
            self.note.set_text("El servicio no está disponible. Inícialo con scripts/run-desktop.sh; la interfaz se reconectará.")
            self.hero_title.set_text("Esperando señal.")
            self.hero_subtitle.set_text("Las lecturas anteriores ya no describen el estado actual.")
            self.wisp.update("unknown", True)
            for metric in self.metrics.values():
                metric.update(None, "—", "sin conexión")
            if self.overlay:
                self.drag_cancel()
                self.overlay.set_visible(False)
            self.ask_button.set_sensitive(False)
            return False
        self.snapshot = value
        for control in (self.motion, self.mute_button):
            control.set_sensitive(True)
        for control in (self.avatar_toggle, self.monitors):
            control.set_sensitive(bool(self.overlay))
            control.set_tooltip_text("Requiere Wayland y gtk4-layer-shell" if not self.overlay else None)
        self.connection.set_text("MODO DEMO" if self.args.demo else "●  SISTEMA CONECTADO")
        self.connection.remove_css_class("offline")
        self.ask_button.set_sensitive(not self.is_asking)
        domains, prefs = value["domains"], value["preferences"]
        def current(domain):
            item = domains.get(domain, {})
            return item.get("value", {}) if item.get("fresh") else {}
        system = current("system")
        for key, field in (("cpu", "cpu_ratio"), ("memory", "memory_ratio")):
            v = system.get(field)
            self.metrics[key].update(v, f"{v*100:.0f}%" if v is not None else "—", "en uso" if v is not None else "sin lectura")
        v = system.get("temperature_c")
        self.metrics["temperature"].update(v/100 if v is not None else None, f"{v:.0f}°" if v is not None else "—", "Celsius" if v is not None else "sin sensor")
        mounts = current("storage").get("mounts", [])
        mount = min(mounts, key=lambda x: x["ratio"]) if mounts else None
        self.metrics["storage"].update(mount["ratio"] if mount else None, f"{mount['available']/1024**3:.0f}" if mount else "—", "GiB libres" if mount else "sin lectura")
        presence = value["presence"]
        title, subtitle = {
            "idle": ("Todo en equilibrio.", "No hay alertas activas en las fuentes disponibles."),
            "media": ("A tu ritmo.", "La música sigue. Yo observo el sistema."),
            "busy": ("Trabajo en marcha.", "El sistema está ocupado. Estoy siguiendo su evolución."),
            "warning": ("Algo merece\ntu atención.", "Tengo una observación para ti. Puedes revisar la evidencia aquí."),
            "unknown": ("Buscando señal.", "Espero lecturas recientes antes de sacar conclusiones."),
        }[presence]
        self.hero_title.set_text(title); self.hero_subtitle.set_text(subtitle)
        self.wisp.update(presence, prefs["reduced_motion"], value)
        media = current("media")
        self.media_label.set_text("♫  " + (media.get("title") or "Reproducción activa") if media.get("status") == "playing" else "◌  Sin reproducción activa")
        desk = current("desktop")
        self.desktop_label.set_text(f"{desk.get('monitor', 'ESCRITORIO')}  /  {desk.get('workspace', '—')}")
        self.updating = True
        self.motion.set_active(prefs["reduced_motion"])
        self.avatar_toggle.set_active(prefs["avatar_visible"])
        self.mute_button.set_label("Reactivar avisos" if prefs["muted_until"] > time.time() else "Silenciar avisos · 1 h")
        options = ["", *desk.get("outputs", [])]
        if options != self.monitor_options:
            self.monitor_options = options
            self.monitors.set_model(Gtk.StringList.new(["Automático · pantalla sin foco", *options[1:]]))
        self.monitors.set_selected(options.index(prefs["monitor"]) if prefs["monitor"] in options else 0)
        self.updating = False
        issues = [x for x in value["insights"] if x["status"] != "resolved"]
        self.count.set_text(f"{len(issues):02d} OBSERVACIONES")
        signature = [(i["id"], i["status"], i["acknowledged"], i["snoozed_until"]) for i in issues]
        if signature != self.issue_signature:
            self.issue_signature = signature
            self.render_issues(issues)
        if value["history"] != self.history_signature:
            self.history_signature = value["history"]
            self.render_history(value["history"])
        if value["health"] != self.health_signature:
            self.health_signature = value["health"]
            self.render_health(value["health"])
        self.ai_info.set_text("IA local · " + value["assistant"]["model"] if value["assistant"]["enabled"] else "IA opcional sin configurar · explicaciones locales disponibles")
        if not value["durable"]:
            self.note.set_text("Historial no disponible · monitoreo temporal en memoria")
        elif self.args.demo:
            self.note.set_text("DEMOSTRACIÓN · Datos de ejemplo · Interfaz nativa de Wisp 0.14")
        else:
            self.note.set_text("Procesamiento local · Sin acciones automáticas sobre tu sistema")
        session = current("session")
        if session.get("locked") is True:
            self.window.set_visible(False)
            self.explicit_open = False
            self.answer_generation += 1
            self.response_box.set_visible(False)
        if self.overlay:
            if self.pending_drag_prefs:
                if all(prefs.get(k) == v for k, v in self.pending_drag_prefs.items()):
                    self.pending_drag_prefs = None
                else:
                    prefs = dict(prefs, **self.pending_drag_prefs)
            display = Gdk.Display.get_default()
            monitors = display.get_monitors()
            connected = {m.get_connector(): m for m in monitors}
            current_monitor = Layer.get_monitor(self.overlay)
            name = companion_monitor(connected, desk.get("monitor"), prefs["monitor"],
                                     current_monitor.get_connector() if current_monitor else None)
            selected = connected.get(name)
            if self.dragging:
                selected = Layer.get_monitor(self.overlay)
            if selected and not self.dragging and Layer.get_monitor(self.overlay) != selected:
                Layer.set_monitor(self.overlay, selected)
            if selected and not self.dragging:
                geometry = selected.get_geometry()
                Layer.set_margin(self.overlay, Layer.Edge.RIGHT, min(prefs["margin_x"], max(0, geometry.width-self.avatar.get_width())))
                Layer.set_margin(self.overlay, Layer.Edge.BOTTOM, min(prefs["margin_y"], max(0, geometry.height-self.avatar.get_height())))
            self.avatar.update(presence, prefs["reduced_motion"], value)
            for _, preview, *_ in self.drag_previews:
                preview.update(presence, prefs["reduced_motion"], value)
            fullscreen = desk.get("fullscreen") and (not selected or selected.get_connector() == desk.get("monitor"))
            show = prefs["avatar_visible"] and session.get("locked") is False and not fullscreen
            if not show:
                self.drag_cancel()
            self.overlay.set_visible(show)
        return False

    def render_issues(self, issues):
        clear(self.issues)
        if not issues:
            calm = box(True, 9, "insight")
            calm.append(label("◈  Sin alertas activas", "insight-title"))
            calm.append(label("Las fuentes disponibles siguen bajo observación.", "muted", True))
            self.issues.append(calm)
        for item in issues[:8]:
            card = box(True, 8, "insight"); card.add_css_class(item["severity"])
            row = box(False, 10)
            text = label(item["title"], "insight-title", True); text.set_hexpand(True); row.append(text)
            tag = "SIN LECTURA" if item["status"] == "unknown" else "POSPUESTO" if item["snoozed_until"] > time.time() else "REVISADO" if item["acknowledged"] else "ATENCIÓN"
            row.append(label(tag, "tag")); card.append(row)
            e = item["evidence"]
            val = e["value"]*100 if "%" in e["unit"] else e["value"]
            card.append(label(f"{e['subject']} · {val:.1f} {e['unit']} · lectura que originó la observación", "evidence", True))
            actions = box(False, 6)
            actions.append(button("Ver evidencia ↗", lambda _, ident=item["id"]: self.open_insight(ident), "mini"))
            actions.append(button("Posponer 30 min", lambda _, ident=item["id"]: self.submit("insight.snooze", {"id": ident, "seconds": 1800}), "mini flat"))
            actions.append(button("Revisado", lambda _, ident=item["id"]: self.submit("insight.acknowledge", {"id": ident}), "mini flat"))
            card.append(actions); self.issues.append(card)

    def render_history(self, events):
        clear(self.history)
        self.history.append(label("Actividad reciente", "section-title"))
        if not events:
            self.history.append(label("Aquí aparecerán las observaciones y recuperaciones.", "muted", True))
        for item in events[:30]:
            card = box(True, 6, "insight")
            card.append(label(item["title"], "insight-title", True))
            state = {"active": "Detectado", "resolved": "Recuperación confirmada", "unknown": "Lectura no disponible"}.get(item["status"], item["status"])
            card.append(label(time.strftime("%H:%M", time.localtime(item["at"])) + "  ·  " + state, "tag-good" if item["status"] == "resolved" else "muted"))
            self.history.append(card)

    def render_health(self, health):
        clear(self.health_box)
        names = {"system": "Sistema", "storage": "Almacenamiento", "network": "Red local", "media": "Reproducción", "desktop": "Hyprland", "session": "Sesión", "virtualization": "Máquinas virtuales", "persistence": "Historial", "notifications": "Avisos"}
        for key, value in health.items():
            row = box(False, 12)
            text = label(names.get(key,key), "insight-title"); text.set_hexpand(True); row.append(text)
            row.append(label("● Disponible" if value["state"] == "healthy" else "○ No disponible", "tag-good" if value["state"] == "healthy" else "muted"))
            row.set_tooltip_text(value.get("message", ""))
            self.health_box.append(row)

    def open_insight(self, ident):
        self.answer_generation += 1
        self.submit("insight.explain", {"id": ident}, self.show_response)

    def mute(self, *_):
        muted = bool(self.snapshot and self.snapshot["preferences"]["muted_until"] > time.time())
        self.submit("attention.mute", {"seconds": 0 if muted else 3600})

    def motion_changed(self, widget, *_):
        if not self.updating:
            self.submit("preferences.set", {"reduced_motion": widget.get_active()})

    def monitor_changed(self, widget, *_):
        index = widget.get_selected()
        if not self.updating and index < len(self.monitor_options):
            self.pending_drag_prefs = None
            self.submit("preferences.set", {"monitor": self.monitor_options[index]})

    def avatar_changed(self, widget):
        if not self.updating:
            self.submit("preferences.set", {"avatar_visible": widget.get_active()})

    def ask(self, *_):
        if self.is_asking or not self.snapshot:
            return
        question = self.question.get_text().strip() or "¿Cómo está mi sistema?"
        self.is_asking = True
        self.answer_generation += 1
        generation = self.answer_generation
        self.ask_button.set_sensitive(False)
        self.response_title.set_text("REVISANDO TU CONTEXTO")
        self.response_text.set_text("Un momento…")
        self.response_box.set_visible(True)
        def answered(value, error):
            self.is_asking = False
            self.ask_button.set_sensitive(self.snapshot is not None)
            if generation == self.answer_generation:
                self.show_response(value, error)
            return False
        self.submit("assistant.ask", {"question": question}, answered)

    def dismiss_response(self, *_):
        self.answer_generation += 1
        self.response_box.set_visible(False)
        if self.is_asking:
            self.note.set_text("Respuesta descartada · la consulta local terminará dentro de su plazo")

    def show_response(self, value, error):
        self.response_box.set_visible(True)
        self.response_title.set_text("EXPLICACIÓN LOCAL" if not value or value.get("provider") != "ollama" else "INTERPRETACIÓN · IA LOCAL")
        self.response_text.set_text(error or value.get("text", "Sin respuesta"))
        if value and value.get("note"):
            self.response_title.set_tooltip_text(value["note"])
        return False

    def command_done(self, value, error):
        if error:
            self.note.set_text(error)
        self.poll()
        return False

    def capture(self):
        # Screenshot of the actual GTK widget tree, not an HTML recreation.
        try:
            paintable = Gtk.WidgetPaintable.new(self.window)
            snapshot = Gtk.Snapshot()
            paintable.snapshot(snapshot, self.window.get_width(), self.window.get_height())
            node = snapshot.to_node()
            texture = self.window.get_renderer().render_texture(node, None)
            texture.save_to_png(str(self.args.screenshot))
        except Exception as error:
            print(f"Screenshot: {error}", flush=True)
        if self.args.quit_after_capture:
            self.quit()
        return False

    def shutdown(self, *_):
        self.closed = True
        if self.overlay:
            self.drag_cancel()
            self.popover.unparent()
        self.pool.shutdown(wait=False, cancel_futures=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Clearly labeled sample data; never starts or modifies the daemon")
    parser.add_argument("--no-avatar", action="store_true")
    parser.add_argument("--avatar-only", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--quit-after-capture", action="store_true")
    args = parser.parse_args()
    Gtk.init()
    if Gdk.Display.get_default() is None:
        parser.exit(1, "Wisp necesita una sesión gráfica Wayland o X11 disponible.\n")
    return Application(args).run([])


if __name__ == "__main__":
    raise SystemExit(main())
