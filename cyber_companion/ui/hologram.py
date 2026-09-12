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
    # Match the atlas mesh's yaw and perspective so skin markings stay attached.
    phase = math.tau * frame / (24 if row in (0, 2, 5) else 23)
    yaw = .13 * math.sin(phase)
    def project(x, y, z=12):
        x -= 128
        depth = -x*math.sin(yaw)+z*math.cos(yaw)
        perspective = 230/(230-depth)
        return (128+(x*math.cos(yaw)+z*math.sin(yaw))*perspective,
                90+(y-90)*perspective)

    def vein(points, tint, energy, width=.7):
        # A dark incision underneath the emissive inner edge reads as carved skin.
        cr.new_path()
        for i, point in enumerate(points):
            (cr.move_to if i == 0 else cr.line_to)(*project(*point))
        cr.set_line_width(width+1.1)
        cr.set_source_rgba(.003,.008,.015,.8)
        cr.stroke_preserve()
        cr.set_line_width(width)
        cr.set_source_rgba(*tint, energy)
        cr.stroke()

    # CPU lives in the heart and its branching vessels, without a numeric plaque.
    cpu = signal['cpu']
    heat, limit = signal['temperature'], signal['temperature_limit']
    hot = heat is not None and limit is not None and heat >= limit-7
    tint = (1.,.50,.24) if hot else PALETTE.get(presence, PALETTE['unknown'])
    pulse = 0 if reduced or cpu is None else .5+.5*math.sin(seconds*(2+cpu*5))
    radius = 2.5+(cpu or 0)*3+pulse*.65
    cx, cy = project(128,101,19)
    glow = cairo.RadialGradient(cx,cy,1,cx,cy,15+radius)
    glow.add_color_stop_rgba(0,*tint,.12 if cpu is None else .5+cpu*.35)
    glow.add_color_stop_rgba(1,*tint,0)
    cr.set_source(glow); cr.arc(cx,cy,15+radius,0,math.tau); cr.fill()
    cr.move_to(cx,cy-radius*1.8); cr.line_to(cx+radius,cy)
    cr.line_to(cx,cy+radius*1.8); cr.line_to(cx-radius,cy); cr.close_path()
    cr.set_source_rgba(*tint,.2 if cpu is None else .9); cr.fill()
    for side in (-1,1):
        energy = .14 if cpu is None else .32+cpu*.45+pulse*.12
        vein([(128+side*7,98,15),(128+side*16,91,8),
              (128+side*23,85,2)],tint,energy)
        vein([(128+side*16,91,8),(128+side*17,98,9),
              (128+side*24,105,7)],tint,energy*.7,.5)
        # Memory is a set of tapered gill slits cut into the existing mantle.
        # Their illuminated length grows continuously with use, including true zero.
        for i in range(7):
            y = 107+i*5
            inner = 128+side*(16-i*.7)
            outer = 128+side*(26-i*.7)
            points = [(inner,y,10),(outer,y-5,4)]
            vein(points,(.64,.53,.95),.12,.95)
            amount = 0 if memory is None else max(0,min(1,memory*7-i))
            if amount:
                vein([points[0],(inner+(outer-inner)*amount,y-5*amount,10-6*amount)],
                     (.69,.57,1.),.88,1.05)

    # Horn ridges themselves carry the local-route signal.
    route = signal['route']
    horn = (.29,.87,.94) if route is True else (1.,.55,.27) if route is False else (.33,.39,.47)
    for side in (-1,1):
        vein([(128+side*19,42,8),(128+side*29,35,5),
              (128+side*31,18+(2 if side==1 else 0),-2)],
             horn,.85 if route is not None else .3,.85)

    # A single small forehead glyph replaces the workspace label across the face.
    workspace = str(signal['workspace'])
    if workspace != '—':
        gx, gy = project(128,53,16)
        text(cr,workspace[:3],gx,gy,4.8,(.62,.84,.88),.85,centered=True)

    # Running VMs light vertebrae along the lower central seam (up to six).
    # Exact counts and named workspaces remain available on hover and in the panel.
    vms = signal['running_vms']
    for i in range(6):
        y = 124+i*4.5
        lit = vms is not None and i < vms
        vein([(126.5,y,12),(128,y+1.5,13),(129.5,y,12)],
             (.49,.88,.84),.85 if lit else .10,.9)
    if signal['media']:
        for i in range(4):
            points = []
            for j in range(22):
                t = j/21
                points.append((128+(i-1.5)*5*(1-t)+math.sin(t*6+seconds+i)*4,
                               137+t*30,0))
            vein(points,(.71,.46,1.),.6,.7)
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
