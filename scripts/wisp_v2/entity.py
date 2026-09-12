"""A horned, spectral character: projected obsidian anatomy and signal filaments.

All motion is derived from the existing pose contract and a periodic phase.
The live client adds anatomy-bound telemetry without baking readings into the atlas.
"""
import math
from dataclasses import replace

from PIL import Image, ImageDraw

from .model import COLUMNS, SUPERSAMPLE, TAU, mix_color, pose_for
from .primitives import Canvas, add_glow, finish_frame
from .anatomy import draw_anatomy

CYAN = (67, 227, 242, 255)
VIOLET = (134, 88, 230, 255)


def stroke(draw, canvas, points, color, width=1):
    draw.line([canvas.point(x,y) for x,y in points], fill=color,
              width=max(1,round(width*SUPERSAMPLE)), joint='curve')


def filaments(canvas, phase, color):
    """Unequal signal trails dissolve into packets instead of a body or tail."""
    layer = canvas.layer()
    draw = ImageDraw.Draw(layer)
    for i in range(9):
        points = []
        for j in range(36):
            t = j/35
            x = 128 + (i-4)*4.4*(1-t) + math.sin(t*5+phase+i*.65)*(3+11*t)
            y = 125+t*(32+(i%3)*5)
            points.append((x,y))
        tint = mix_color(color,VIOLET,i/11,round(45+80*canvas.pose.aura))
        stroke(draw,canvas,points,tint,.55 if i%3 else .95)
        for packet in range(2):
            index = int(((phase/TAU+packet*.5+i*.13)%1)*35)
            x,y=points[index]
            stroke(draw,canvas,[(x,y),(x+.5,y+1.6)],(*color[:3],155),.65)
    bloom = canvas.layer()
    add_glow(bloom,layer.getchannel('A'),color,3,.32)
    canvas.composite(bloom)
    canvas.composite(layer)


def orbit(canvas, phase, color, front):
    """Tilted event-horizon ribbon; depth sorting wraps it around the void."""
    layer = canvas.layer()
    draw = ImageDraw.Draw(layer)
    energy = canvas.pose.media*.16 + canvas.pose.data*.10
    for ring in range(3):
        for segment in range(9):
            points=[]
            for j in range(18):
                angle=(segment+j/22)*TAU/9+phase
                is_front=math.sin(angle)>0
                if is_front != front: continue
                radius=44+ring*3+energy*15
                x=math.cos(angle)*radius
                y=math.sin(angle)*(12+ring*2)
                points.append((128+x*.91-y*.45,89+x*.43+y*.90))
            if len(points)>1:
                tint=mix_color(color,VIOLET,ring*.26,150 if front else 62)
                stroke(draw,canvas,points,tint,.7 if ring else 1.1)
    bloom=canvas.layer()
    add_glow(bloom,layer.getchannel('A'),color,2.4,.45)
    canvas.composite(bloom)
    canvas.composite(layer)






def render_frame(state, frame):
    pose=replace(pose_for(state,frame), bob_y=0, tilt=0, scale_y=1)
    canvas=Canvas(pose)
    looping=state in {'idle','working','moving'}
    position=frame/COLUMNS if looping else frame/(COLUMNS-1)
    phase=TAU*(position%1)
    color=mix_color(CYAN,VIOLET,.15+pose.media*.65)
    aura=Image.new('L',canvas.size,0)
    ImageDraw.Draw(aura).ellipse((*canvas.point(94,46),*canvas.point(161,142)),fill=100)
    layer=canvas.layer()
    add_glow(layer,aura,color,15,.28+pose.aura*.15)
    canvas.composite(layer)
    filaments(canvas,phase,color)
    orbit(canvas,phase,color,False)
    draw_anatomy(canvas,phase)
    orbit(canvas,phase,color,True)
    particles=canvas.layer()
    draw=ImageDraw.Draw(particles)
    for i in range(19):
        a=i*2.39996+phase
        radius=49+(i%5)*3
        x,y=128+math.cos(a)*radius,94+math.sin(a)*radius*.9
        stroke(draw,canvas,[(x,y),(x+(1 if i%3 else 3),y)],(*color[:3],65+(i%4)*25),.5)
    canvas.composite(particles)
    return finish_frame(canvas.image)
