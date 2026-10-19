"""Closed mechanical chassis, recessed service routes and thermal returns."""
import math
from mathutils import Vector


def depth(w,d):
    # Platform deck underside is -0.8 m. Every belly extends 1.5 m below it.
    return .8+1.5


def ring(w,d,z,c=.18):
    return [(-w/2+c,-d/2,z),(w/2-c,-d/2,z),(w/2,-d/2+c,z),(w/2,d/2-c,z),
            (w/2-c,d/2,z),(-w/2+c,d/2,z),(-w/2,d/2-c,z),(-w/2,-d/2+c,z)]


def core_points(w,d):
    return ring(w-.06,d-.06,-.76)+ring(w*.70,d*.70,-depth(w,d))


def pad_points(x,y,z):
    # Circumscribed polygon supports the complete authored 5 m mating disc.
    r=2.5/math.cos(math.pi/24)
    return [(x+r*math.cos((i+.5)*math.tau/24),y+r*math.sin((i+.5)*math.tau/24),h)
            for h in (z,z+.20) for i in range(24)]


def pipe(kit,stations,r=.032):
    stations=[Vector(p) for p in stations]
    rings=[]
    for i,p in enumerate(stations):
        tangent=(stations[min(i+1,len(stations)-1)]-stations[max(i-1,0)]).normalized()
        a=tangent.cross(Vector((1,0,0)))
        if a.length<.1:a=tangent.cross(Vector((0,1,0)))
        a.normalize();b=tangent.cross(a).normalized()
        rings.append([p+r*(a*math.cos(j*math.tau/8)+b*math.sin(j*math.tau/8)) for j in range(8)])
    return kit.loft_rings(rings)


def bay_point(length,face_height,side,a,v,z):
    # Follow both the face slope and the narrowing transverse chassis width.
    t=.48-v/face_height
    half=length/2-.03-(length*.15-.03)*t-.22
    return Vector((side*.70*half+a*.32*half,v,z))


def build(k,common,kit,w,d,thrusters,map_detail=False):
    h=depth(w,d)-.76
    core=kit.loft_rings([ring(w-.06,d-.06,-.76),ring(w*.70,d*.70,-depth(w,d))])
    if map_detail:
        # Authorized sockets already lie wholly on the planar chassis belly.
        # The map LOD needs no overlapping discs, micro-hardware or service bays.
        common.emit(k,core,common.SEC,'closed tapered chassis with full planar thruster mounting lands')
        return [core_points(w,d)]
    pads=[kit.loft_rings([pad_points(x,y,-depth(w,d))[:24],pad_points(x,y,-depth(w,d))[24:]])
          for x,y in thrusters]
    core=kit.machine(core,union=pads)
    bays=[]
    frames=[]
    for axis,length,extent in ((0,d,w),(1,w,d)):
        inset=extent*.15-.03
        for sign in (-1,1):
            normal=Vector((0,0,-inset));normal[axis]=sign*h;normal.normalize()
            up=Vector((0,0,h));up[axis]=sign*inset;up.normalize()
            origin=Vector((0,0,-.76-h*.48));origin[axis]=sign*(extent/2-.03-inset*.48)
            frame=common.frame(origin,normal,up)
            face_height=math.hypot(h,inset)
            frames.append((frame,length,face_height))
            for side in (-1,1):
                ah=face_height*.65
                outline=[frame@bay_point(length,face_height,side,a,b*ah,z) for a,b,z in ring(1,1,-.075,.04)]
                bays.append((outline,normal,.35))
    core=kit.machine(core,subtract=bays)
    common.emit(k,core,common.SEC,'closed tapered chassis with quarter-metre recessed service bays')
    proxies=[core_points(w,d)]+[pad_points(x,y,-depth(w,d)) for x,y in thrusters]
    for frame,length,face_height in frames:
        # A sealed access door follows the actual slope.
        pw=min(2.8,length*.36);ph=min(1.8,face_height*.50)
        with k.frame(frame):
            panel=kit.loft_rings([ring(pw,ph,-.014,.09),ring(pw,ph,.065,.09)])
            cuts=[((0,v,.065),(pw*.64,.055,.075)) for v in (-ph*.23,0,ph*.23)]
            panel=kit.machine(panel,boxes=cuts)
            common.emit(k,panel,common.PRI,'closed recessed service panel on tapered chassis')
            for u in (-pw*.40,pw*.40):
                for v in (-ph*.36,ph*.36):
                    common.emit(k,common.rod((u,v,.065),(u,v,.079),.034,6),common.JNT,
                                'service panel captive closure fastener')
            for v in (-ph*.23,0,ph*.23):
                common.emit(k,common.block((-pw*.31,v-.025,.0275),(pw*.31,v+.025,.0325)),
                            common.FRM,'sealed service-panel slot backing')
            # Protected supply/return ports feed a supported closed thermal loop.
            u=pw*.28;v=-ph*.35;bottom=-ph*.60
            for x in (-u,u):
                common.emit(k,common.rod((x,v,.065),(x,v,.12),.058,8),common.JNT,
                            'thermal collector sealed bulkhead coupling')
            common.emit(k,pipe(kit,[(-u,v,.085),(-u,v,.16),(-u,bottom+.07,.16),
                                  (-u+.07,bottom,.16),(u-.07,bottom,.16),(u,bottom+.07,.16),
                                  (u,v,.16),(u,v,.085)]),common.JNT,
                        'supported thermal return between paired service ports')
            common.emit(k,common.block((-.065,bottom-.045,-.015),(.065,bottom+.045,.142)),
                        common.FRM,'thermal return retaining saddle seated on chassis')
            # Each open service bay has a sealed 0.25 m deep back wall.
            # Pipe fittings and cable terminals enter the bay's end walls.
            for side in (-1,1):
                ah=face_height*.65
                def at(a,v,z):return bay_point(length,face_height,side,a,v,z)
                common.emit(k,common.rod(at(-.20,-ah*.51,-.13),at(-.20,ah*.51,-.13),.045,8),
                            common.JNT,'recessed thermal line between bulkhead fittings')
                for v in (-ah*.47,ah*.47):
                    common.emit(k,common.rod(at(-.20,v-.04,-.13),at(-.20,v+.04,-.13),.071,6),
                                common.JNT,'service-bay pipe compression union')
                common.emit(k,pipe(kit,[at(.22,-ah*.51,-.12),at(.27,-ah*.20,-.12),
                                      at(.18,ah*.18,-.12),at(.22,ah*.51,-.12)],r=.017),
                            common.FRM,'recessed power loom joining sealed cable terminals')
                for v in (-ah*.49,ah*.49):
                    x=at(.22,v,-.12).x
                    common.emit(k,common.block((x-.045,v-.04,-.25),(x+.045,v+.04,-.10)),
                                common.FRM,'service loom end-wall feedthrough')
                for a,hw,hy,z,tag in ((-.20,.075,.045,-.12,'thermal-line retaining saddle'),
                                      (.22,.075,.04,-.105,'loom retaining clip')):
                    x=at(a,0,z).x
                    common.emit(k,common.block((x-hw,-hy,-.25),(x+hw,hy,z)),common.SEC,
                                tag+' on closed bay back wall')
        proxies.append([list(frame@Vector((u,v,z)))
                        for u in (-length*.43,length*.43) for v in (-face_height*.42,face_height*.42)
                        for z in (-.015,.20)])
    return proxies
