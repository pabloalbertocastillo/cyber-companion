"""Cairo holographic instrumentation. Consumes snapshots; never samples the host."""
import math


PALETTE = {
    "idle": (.27, .94, .85), "media": (.72, .50, 1.),
    "busy": (.30, .72, 1.), "warning": (1., .65, .30),
    "unknown": (.47, .58, .66),
}


def fresh(snapshot, name):
    domain = (snapshot or {}).get("domains", {}).get(name, {})
    return domain.get("value", {}) if domain.get("fresh") else {}


def telemetry(snapshot):
    system, desktop = fresh(snapshot, "system"), fresh(snapshot, "desktop")
    network, media = fresh(snapshot, "network"), fresh(snapshot, "media")
    mounts = fresh(snapshot, "storage").get("mounts", [])
    lowest = min(mounts, key=lambda x: x["ratio"]) if mounts else None
    virtualization = fresh(snapshot, "virtualization")
    running = sum(vm["state"] == "running" for vm in virtualization["vms"]) if "vms" in virtualization else None
    route = network.get("default_route")
    return {"cpu": system.get("cpu_ratio"), "memory": system.get("memory_ratio"),
            "temperature": system.get("temperature_c"), "workspace": desktop.get("workspace", "—"),
            "temperature_limit": system.get("temperature_limit_c"), "route": route,
            "network": "NET OK" if route is True else "NO ROUTE" if route is False else "NET —",
            "media": media.get("status") == "playing", "running_vms": running,
            "storage": lowest}


def anatomy_scale(signal, hovered=False, reduced=False):
    """Bounded visible size; anatomical readouts share the character transform."""
    if reduced:
        return .96
    cpu = signal['cpu'] if signal['cpu'] is not None else 0
    memory = signal['memory'] if signal['memory'] is not None else 0
    return min(1.13, .90 + .15*cpu + .06*memory + (.055 if hovered else 0))


def paint_entity(cr, atlas, row, frame, width, height, signal, seconds,
                 size=1, look=(0,0), reduced=False, presence="idle"):
    """Living anatomical accents in atlas coordinates, driven only by fresh data."""
    import cairo
    scale=min(width/256,height/192)*.98*size
    x,y=(width-256*scale)/2,height*.50-192*scale/2
    cr.save()
    cr.translate(x,y)
    cr.scale(scale,scale)
    cr.translate(128,98)
    cr.transform(cairo.Matrix(xx=1, yx=look[0]*.018, xy=look[0]*.045, yy=1))
    cr.translate(-128+look[0]*2,-98+look[1]*1.2)
    # A soft darkness field plus an offset silhouette reads on both light and dark.
    shade=cairo.RadialGradient(128,102,18,128,102,78)
    shade.add_color_stop_rgba(0,.005,.009,.018,.70)
    shade.add_color_stop_rgba(.5,.005,.009,.018,.44)
    shade.add_color_stop_rgba(1,.005,.009,.018,0)
    cr.set_source(shade); cr.rectangle(45,18,170,166); cr.fill()
    cr.save()
    cr.rectangle(0,0,256,192); cr.clip()
    cr.set_source_rgba(0,0,0,.6)
    cr.mask_surface(atlas,-frame*256+3,-row*192+4)
    # Memory opens and illuminates the spectral folds. Unknown is a dim outline.
    memory=signal['memory']
    spread=4+(memory or 0)*13
    for side in (-1,1):
        cr.move_to(128+side*21,81)
        cr.line_to(128+side*(35+spread),103)
        cr.line_to(128+side*(24+spread),141)
        cr.line_to(128+side*8,166)
        cr.line_to(128+side*21,118)
        cr.close_path()
        cr.set_source_rgba(.025,.035,.08,.75); cr.fill_preserve()
        cr.set_source_rgba(.52,.40,.86,.12 if memory is None else .22+memory*.48)
        cr.set_line_width(.65); cr.stroke()
    cr.set_source_surface(atlas,-frame*256,-row*192)
    cr.paint()
    cr.restore()
    # CPU lives in the heart. No data means no pulse, rather than fake idleness.
    cpu=signal['cpu']
    heat=signal['temperature']
    limit=signal['temperature_limit']
    hot=heat is not None and limit is not None and heat >= limit-7
    tint=(1.,.50,.24) if hot else (.30,.91,.94)
    pulse=0 if reduced or cpu is None else .5+.5*math.sin(seconds*(2+cpu*5))
    radius=2.5+(cpu or 0)*3+pulse*.65
    glow=cairo.RadialGradient(128,101,1,128,101,15+radius)
    glow.add_color_stop_rgba(0,*tint,.12 if cpu is None else .5+cpu*.35)
    glow.add_color_stop_rgba(1,*tint,0)
    cr.set_source(glow); cr.arc(128,101,15+radius,0,math.tau); cr.fill()
    cr.move_to(128,101-radius*1.8); cr.line_to(128+radius,101)
    cr.line_to(128,101+radius*1.8); cr.line_to(128-radius,101); cr.close_path()
    cr.set_source_rgba(*tint,.2 if cpu is None else .85); cr.fill()
    if cpu is not None:
        cr.set_source_rgba(.84,.99,1.,.8)
        cr.set_line_width(.7); cr.move_to(128,97);cr.line_to(128,105);cr.stroke()
    # Swept horns are local-route antennae; this does not assert Internet access.
    route=signal['route']
    horn=(.29,.87,.94) if route is True else (1.,.55,.27) if route is False else (.33,.39,.47)
    for side in (-1,1):
        cr.move_to(128+side*19,43)
        cr.line_to(128+side*29,35)
        cr.line_to(128+side*31,20+(2 if side==1 else 0))
        cr.set_source_rgba(*horn,.85 if route is not None else .3)
        cr.set_line_width(.85);cr.stroke()
    if signal['media']:
        for i in range(4):
            cr.new_path()
            for j in range(22):
                t=j/21
                x=128+(i-1.5)*5*(1-t)+math.sin(t*6+seconds+i)*4
                y=130+t*37
                (cr.move_to if j==0 else cr.line_to)(x,y)
            cr.set_source_rgba(.71,.46,1.,.6); cr.set_line_width(.7);cr.stroke()
    insignia(cr, signal, presence, seconds)
    cr.restore()


def text(cr, value, x, y, size, color, alpha=1, centered=False):
    cr.select_font_face("monospace")
    cr.set_font_size(size)
    cr.set_source_rgba(*color, alpha)
    if centered:
        extent = cr.text_extents(value)
        x -= extent.width / 2 + extent.x_bearing
    cr.move_to(x, y)
    cr.text_path(value)
    cr.set_line_width(1.5)
    cr.set_source_rgba(.005,.01,.02,.78*alpha)
    cr.stroke_preserve()
    cr.set_source_rgba(*color,alpha)
    cr.fill()


def insignia(cr, signal, presence, seconds):
    """Readings engraved into the mantle, sharing all character motion."""
    color = PALETTE.get(presence, PALETTE["unknown"])
    for side, key, title, tint in ((-1, "cpu", "CPU", color),
                                    (1, "memory", "RAM", (.72,.61,1.))):
        center = 128+side*20
        # Faceted inlays follow the mantle instead of orbiting the silhouette.
        cr.move_to(center-17, 114); cr.line_to(center, 110)
        cr.line_to(center+17, 114); cr.line_to(center+14, 141)
        cr.line_to(center, 150); cr.line_to(center-14, 141); cr.close_path()
        cr.set_source_rgba(.012,.024,.043,.94); cr.fill_preserve()
        cr.set_source_rgba(*tint,.4); cr.set_line_width(.6); cr.stroke()
        value = signal[key]
        text(cr, title, center, 121, 6.3, tint, centered=True)
        text(cr, "—" if value is None else f"{value*100:.0f}%",
             center, 133, 8.4, (.87,.95,1.), centered=True)
        for i in range(8):
            filled = value is not None and (i+.5)/8 <= value
            cr.set_source_rgba(*tint, .95 if filled else .15)
            cr.rectangle(center-11+i*3, 138, 2, 3); cr.fill()
    # Workspace is a mask engraving. The local route lives at the collar/horns.
    text(cr, "WS "+str(signal["workspace"])[:5], 128, 74, 6.4,
         (.80,.91,.95), centered=True)
    route = signal["route"]
    tint = (.43,.95,.83) if route is True else (1.,.65,.30) if route is False else PALETTE["unknown"]
    text(cr, signal["network"], 128, 87, 6.1, tint, centered=True)
    vms = "—" if signal["running_vms"] is None else str(signal["running_vms"])
    text(cr, 'VM '+vms, 128, 157, 6.8, color, centered=True)
    if signal["media"]:
        for i in range(7):
            h = 2+4*(.5+.5*math.sin(seconds*3+i*.8))
            cr.set_source_rgba(.76,.57,1.,.85)
            cr.rectangle(118+i*3, 164-h, 1.5, h); cr.fill()
