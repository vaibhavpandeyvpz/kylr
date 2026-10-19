"""Floor seams and convex walls preserve the entry, duplex rooms and lift void."""
from mathutils import Vector
import model as source

def octagon(w,c):
    # The render generator sets its shared outline helper to one chamfer step,
    # but collision runs in a fresh Blender process where that helper defaults
    # to three. Never let mutable preview settings change the eight wall edges.
    r=w/2
    return [(r,r-c),(r-c,r),(-r+c,r),(-r,r-c),
            (-r,-r+c),(-r+c,-r),(r-c,-r),(r,-r+c)]
def slab(p,z0,z1,bone='Root'):return hull([(x,y,z) for z in (z0,z1) for x,y in p],bone)

def blockers():
    result=[slab(octagon(13.8,.65),0,.08)]
    result.extend([slab([(-6.9,-6.25),(-6.25,-6.9),(-2.65,-6.9),(-2.65,6.9),(-6.25,6.9),(-6.9,6.25)],.08,.32),
        slab([(2.65,-6.9),(6.25,-6.9),(6.9,-6.25),(6.9,6.25),(6.25,6.9),(2.65,6.9)],.08,.32),
        box((-2.65,6.5,.08),(2.65,6.9,.32)),box((-1.52,-6.9,.08),(1.52,2.38,.32)),
        box((-2.65,-6.9,.08),(-1.52,5.4,.32)),box((1.52,-6.9,.08),(2.65,5.4,.32))])
    result.append(hull([(x,y,z) for x in (-source.RAMP_WIDTH/2,source.RAMP_WIDTH/2) for y,z in ((-7.5,0),(-6.9,.32),(-6.9,0))]))
    outer,inner=octagon(14.7,.85),octagon(13.8,.65)
    for i in range(8):
        if i==5:continue
        j=(i+1)%8
        result.append(slab([outer[i],outer[j],inner[j],inner[i]],0,.56))
    result.extend([box((-6.5,-7.35,0),(-source.RAMP_WIDTH/2,-6.9,.56)),box((source.RAMP_WIDTH/2,-7.35,0),(6.5,-6.9,.56))])
    result.extend([slab([(-6.5,-5.85),(-5.85,-6.5),(-2.65,-6.5),(-2.65,6.5),(-5.85,6.5),(-6.5,5.85)],4.08,4.32),
       slab([(2.65,-6.5),(5.85,-6.5),(6.5,-5.85),(6.5,5.85),(5.85,6.5),(2.65,6.5)],4.08,4.32),
       box((-2.65,-6.5,4.08),(-1.52,5.4,4.32)),box((1.52,-6.5,4.08),(2.65,5.4,4.32)),
       box((-1.52,-6.5,4.08),(1.52,2.38,4.32))])
    for z0,z1,outer0,outer1,inner0,inner1 in (
        (.32,2.98,13.8,13.8,13.0,13.0),(2.98,3.62,13.8,13.4,13.0,13.0),
        (3.62,6.98,13.4,13.4,13.0,13.0),
        (6.98,7.70,13.4,12.8,13.0,12.05)):
        a,b,c,d=octagon(outer0,.65),octagon(outer1,.65),octagon(inner0,.65),octagon(inner1,.65)
        for i in range(8):
            j=(i+1)%8
            if z0<6.98 and i==5:continue
            result.append(hull([(x,y,z) for z,poly in ((z0,a),(z1,b),(z0,c),(z1,d)) for x,y in (poly[i],poly[j])]))
    result.extend([box((-6.25,-6.9,.32),(-(2.89*source.door.ENTRY_RESIZE[0][0]),-6.5,3.64)),box((2.89*source.door.ENTRY_RESIZE[0][0],-6.9,.32),(6.25,-6.5,3.64)),
       box((-6.05,-6.7,3.64),(-(2.89*source.door.ENTRY_RESIZE[0][0]),-6.5,4.39)),box((2.89*source.door.ENTRY_RESIZE[0][0],-6.7,3.64),(6.05,-6.5,4.39)),
       box((-6.05,-6.7,4.39),(6.05,-6.5,6.98))])
    result.append(box((-2.89*source.door.ENTRY_RESIZE[0][0],-6.9,source.GROUND+3.48*source.door.ENTRY_RESIZE[2][2]+.59*source.door.ENTRY_RESIZE[2][2]),(2.89*source.door.ENTRY_RESIZE[0][0],-6.5,3.64)))
    result.append(slab(octagon(12.6,.65),7.70,8.22))
    outer=source.door.portal_offset(.59);inner=source.door.PORTAL
    for i in range(1,8):
        j=(i+1)%8
        result.append(hull([source.ENTRY_FRAME@Vector((x,y,z)) for y in (-2.31,-2.15) for x,z in (outer[i],outer[j],inner[i],inner[j])]))
    for s,bone in ((1,'LeftDoor'),(-1,'RightDoor')):
        result.append(hull([source.ENTRY_FRAME@Vector((x,y,z)) for y in (-2.33,source.door.DOOR_BACK) for x,z in source.door.half_leaf(s)],bone))
    result.append(box((-1.5,2.4,.12),(1.5,5.4,.32),'CargoLift'))
    for s in (-1,1):
        x=s*1.68;result.append(box((x-.045,2.4,4.32),(x+.045,5.3,5.40)))
    return result

def trigger():return [box((-1.48,2.42,.32),(1.48,5.38,.48),'CargoLift')]
