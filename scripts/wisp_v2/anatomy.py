"""Projected, depth-sorted obsidian anatomy with directional facet lighting."""
import math
from PIL import ImageDraw


def mesh(canvas, vertices, faces, phase, tint=(34, 48, 65), edge=(56, 143, 166)):
    yaw = .13 * math.sin(phase)
    transformed = []
    for x, y, z in vertices:
        x -= 128
        transformed.append((x*math.cos(yaw)+z*math.sin(yaw), y,
                            -x*math.sin(yaw)+z*math.cos(yaw)))
    def project(v):
        x,y,z=v
        perspective=230/(230-z)
        return canvas.point(128+x*perspective,90+(y-90)*perspective)
    layer=canvas.layer()
    draw=ImageDraw.Draw(layer)
    for face in sorted(faces,key=lambda f:sum(transformed[i][2] for i in f)/len(f)):
        a,b,c=[transformed[i] for i in face[:3]]
        u=[b[i]-a[i] for i in range(3)]; v=[c[i]-a[i] for i in range(3)]
        n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        length=math.sqrt(sum(k*k for k in n)) or 1
        n=[k/length for k in n]
        if n[2]<0: n=[-k for k in n]
        illumination=max(0,-.45*n[0]-.60*n[1]+.65*n[2])
        light=.23+.95*illumination
        fill=tuple(min(255,int(k*light)) for k in tint)+(255,)
        points=[project(transformed[i]) for i in face]
        draw.polygon(points,fill=fill)
        draw.line(points+[points[0]],fill=(*edge,70+int(55*illumination)),width=2)
    canvas.composite(layer)


def mantle(canvas, phase):
    # A continuous shoulder/chest volume, then split spectral folds below it.
    flare=2*canvas.pose.data+4*canvas.pose.media
    vertices=[(128,76,6),(107-flare,79,0),(89-flare,89,-5),(103,102,7),
              (111,121,7),(102-flare,151,-4),(122,135,12),(128,98,18),
              (149+flare,79,0),(167+flare,89,-5),(153,103,6),
              (146,123,6),(154+flare,149,-5),(134,137,12),
              (121,169,-10),(139,159,-8)]
    faces=[(0,1,3,7),(1,2,3),(2,5,4,3),(3,4,6,7),(4,5,14,6),
           (0,7,10,8),(8,10,9),(9,10,11,12),(7,6,13),(7,13,11,10),
           (11,13,15,12),(6,14,13),(13,14,15)]
    mesh(canvas,vertices,faces,phase,tint=(31,43,61),edge=(38,113,141))


def mask(canvas, phase):
    # Narrow, elongated ritual mask; proportions avoid the original chibi head.
    vertices=[(128,39,1),(111,45,2),(109,58,4),(113,70,5),(128,85,7),
              (144,70,5),(148,56,2),(143,43,0),(128,49,16),
              (117,59,17),(128,66,21),(140,57,17),(128,77,13)]
    faces=[(0,1,8),(0,8,7),(1,2,9,8),(7,8,11,6),(8,9,10),(8,10,11),
           (2,3,9),(6,11,5),(9,3,12,10),(10,12,5,11),(3,4,12),(4,5,12)]
    mesh(canvas,vertices,faces,phase,tint=(48,58,77),edge=(55,141,160))
    # Dark slanted recesses, not oversized glowing cartoon eyes.
    layer=canvas.layer(); draw=ImageDraw.Draw(layer)
    for shape in (((114,57),(123,61),(120,64),(113,60)),
                  ((133,61),(143,55),(143,60),(135,64))):
        draw.polygon([canvas.point(*p) for p in shape],fill=(1,5,11,250))
    # Central split and lower contours make the mask feel carved and hollow.
    draw.line([canvas.point(128,47),canvas.point(127,59),canvas.point(130,68),canvas.point(128,78)],
              fill=(86,175,186,155),width=2)
    canvas.composite(layer)


def horns(canvas, phase):
    for side in (-1,1):
        # Swept asymmetric horns double as connection antennae in the live view.
        shift=2 if side==1 else 0
        vertices=[(128+side*15,51,0),(128+side*27,43,-1),
                  (128+side*34,24+shift,-3),(128+side*31,18+shift,-2),
                  (128+side*29,35,5),(128+side*19,42,8),
                  (128+side*33,41,-6)]
        faces=[(0,1,5),(1,4,5),(1,6,2,4),(4,2,3),(0,5,4)]
        mesh(canvas,vertices,faces,phase,tint=(46,52,75),edge=(58,129,158))


def core_socket(canvas, phase):
    vertices=[(128,88,15),(118,98,14),(123,112,14),(128,119,11),
              (134,111,14),(139,98,12),(128,101,19)]
    faces=[(0,1,6),(0,6,5),(1,2,6),(2,3,6),(3,4,6),(4,5,6)]
    mesh(canvas,vertices,faces,phase,tint=(8,18,31),edge=(49,174,187))


def draw_anatomy(canvas, phase):
    mantle(canvas,phase)
    horns(canvas,phase)
    mask(canvas,phase)
    core_socket(canvas,phase)
