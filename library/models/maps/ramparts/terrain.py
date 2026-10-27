"""Deterministic closed Martian mesas with protected native fixture seats.

A radial surface supports eroded shoulders and cliff undercuts which a single
height field cannot represent. Render and collision consume the same vertices.
"""
import math
from layout import HEIGHT, ROCK_BOTTOM, settings, data


def geometry(center, seed):
    recipe=settings()['terrain'];n=recipe['segments'];rings=recipe['summit_rings']
    seats=[]
    for m in data()[1]:
        if m.get('deck') not in ('A_Mainland','B_Mainland'):continue
        if abs(m['position_blender'][0]-center[0])>20:continue
        radius=8.0 if m.get('source_asset',m['asset'])=='cistern' else 1.6
        seats.append((*m['position_blender'][:2],radius+recipe['fixture_seat_margin_m']))
    def outline(a):
        c,s=math.cos(a),math.sin(a)
        # Rounded corners and unequal bays replace the square cutting plane.
        radius=12.5/(abs(c)**8+abs(s)**8)**.125
        return radius+recipe['shoulder_m']+.42*math.sin(5*a+seed)+.24*math.sin(13*a+seed*.3)
    def elevation(x,y,t,a):
        seat=min((max(0,math.hypot(x-sx,y-sy)-r) for sx,sy,r in seats),default=10)
        influence=min(1,seat/1.3);influence=influence*influence*(3-2*influence)
        erosion=recipe['rim_drop_m']*max(0,(t-.7)/.3)**1.4
        shallow=.13*(.5+.5*math.sin(x*.8+y*.57+seed))*min(1,t*3)
        return HEIGHT-influence*(erosion+shallow)
    verts=[(center[0],center[1],HEIGHT)];faces=[]
    for ring in range(1,rings+1):
        t=ring/rings
        for i in range(n):
            a=math.tau*i/n;r=outline(a)*t;x=center[0]+math.cos(a)*r;y=center[1]+math.sin(a)*r
            verts.append((x,y,elevation(x,y,t,a)))
    for i in range(n):faces.append((0,1+i,1+(i+1)%n))
    for ring in range(rings-1):
        a=1+ring*n;b=a+n
        for i in range(n):
            j=(i+1)%n
            faces.extend(((a+i,b+i,b+j),(a+i,b+j,a+j)))
    # Short sloping shoulders blend into deeply weathered, stratified faces.
    levels=[(HEIGHT-1.3,1.02),(HEIGHT-3.2,.98),(HEIGHT-5.8,1.08),
            (1.0,1.14),(-4.8,1.20),(ROCK_BOTTOM,1.24)]
    previous=1+(rings-1)*n
    for level,(z,scale) in enumerate(levels):
        start=len(verts)
        for i in range(n):
            a=math.tau*i/n
            rough=.4*math.sin(a*11+seed)+.24*math.sin(a*23+seed*.7)
            r=outline(a)*scale+rough
            zz=z if level==len(levels)-1 else z+.18*math.sin(a*9+seed+level)
            verts.append((center[0]+math.cos(a)*r,center[1]+math.sin(a)*r,zz))
        for i in range(n):
            j=(i+1)%n
            faces.extend(((previous+i,start+i,start+j),(previous+i,start+j,previous+j)))
        previous=start
    faces.append(tuple(reversed(range(previous,previous+n))))
    return verts,faces
