"""Floor seams and convex walls preserve the entry, duplex rooms and lift void."""
from mathutils import Vector
import model as source

def octagon(w,c):
    # Structural proxy loops use exactly eight corners, independent of render tessellation.
    r=w/2
    return [(r,r-c),(r-c,r),(-r+c,r),(-r,r-c),(-r,-r+c),(-r+c,-r),(r-c,-r),(r,-r+c)]
def slab(p,z0,z1,bone='Root'):return hull([(x,y,z) for z in (z0,z1) for x,y in p],bone)

def blockers():
    result=[slab(octagon(13.8,1.4),0,.08)]
    result.extend([slab([(-6.9,-5.50),(-5.50,-6.9),(-2.65,-6.9),(-2.65,6.9),(-5.50,6.9),(-6.9,5.50)],.08,.32),
        slab([(2.65,-6.9),(5.50,-6.9),(6.9,-5.50),(6.9,5.50),(5.50,6.9),(2.65,6.9)],.08,.32),
        box((-2.65,6.5,.08),(2.65,6.9,.32)),box((-1.52,-6.9,.08),(1.52,2.38,.32)),
        box((-2.65,-6.9,.08),(-1.52,5.4,.32)),box((1.52,-6.9,.08),(2.65,5.4,.32))])
    result.append(hull([(x,y,z) for x in (-source.RAMP_WIDTH/2,source.RAMP_WIDTH/2) for y,z in ((-7.5,0),(-6.9,.32),(-6.9,0))]))
    outer,inner=octagon(14.7,1.6),octagon(13.8,1.4)
    for i in range(8):
        if i==5:continue
        j=(i+1)%8
        result.append(slab([outer[i],outer[j],inner[j],inner[i]],0,.56))
    result.extend([box((-5.75,-7.35,0),(-source.RAMP_WIDTH/2,-6.9,.56)),box((source.RAMP_WIDTH/2,-7.35,0),(5.75,-6.9,.56))])
    result.extend([slab([(-6.5,-5.10),(-5.10,-6.5),(-2.65,-6.5),(-2.65,6.5),(-5.10,6.5),(-6.5,5.10)],4.08,4.32),
       slab([(2.65,-6.5),(5.10,-6.5),(6.5,-5.10),(6.5,5.10),(5.10,6.5),(2.65,6.5)],4.08,4.32),
       box((-2.65,-6.5,4.08),(-1.52,5.4,4.32)),box((1.52,-6.5,4.08),(2.65,5.4,4.32)),
       box((-1.52,-6.5,4.08),(1.52,2.38,4.32))])
    for z0,z1,outer0,outer1,inner0,inner1 in (
        (.32,3.64,13.8,13.4,13.0,13.0),(3.64,6.98,13.4,13.4,13.0,13.0),
        (6.98,7.70,13.4,12.8,13.0,12.05)):
        a,b,c,d=octagon(outer0,1.4),octagon(outer1,1.4),octagon(inner0,1.4),octagon(inner1,1.4)
        for i in range(8):
            j=(i+1)%8
            if z0<6.98 and i==5:continue
            result.append(hull([(x,y,z) for z,poly in ((z0,a),(z1,b),(z0,c),(z1,d)) for x,y in (poly[i],poly[j])]))
    result.extend([box((-5.50,-6.9,.32),(-.975,-6.5,3.64)),box((.975,-6.9,.32),(5.50,-6.5,3.64)),
       box((-5.30,-6.7,3.64),(5.30,-6.5,4.39)),
       box((-5.30,-6.7,4.39),(5.30,-6.5,6.98))])
    result.append(box((-.975,-6.9,source.GROUND+(source.ENTRY_TOP+.30-source.GROUND)*source.ENTRY_RESIZE[2][2]),(.975,-6.5,3.64)))
    result.append(slab(octagon(12.6,1.4),7.70,8.22))
    outer=source.portal_outline(.30);inner=source.portal_outline()
    for i in range(1,len(inner)):
        j=(i+1)%len(inner)
        result.append(hull([source.ENTRY_RESIZE@Vector((x,y,z)) for y in (-6.98,-6.5) for x,z in (outer[i],outer[j],inner[i],inner[j])]))
    leaf=[(x-(.008 if x>0 else -.008),z+.008 if z==source.GROUND else z-.008) for x,z in inner]
    result.append(hull([source.ENTRY_RESIZE@Vector((x,y,z)) for y in (-6.53,-6.37) for x,z in leaf],'Door'))
    result.append(box((-1.5,2.4,.12),(1.5,5.4,.32),'CargoLift'))
    for s in (-1,1):
        x=s*1.68;result.append(box((x-.045,2.4,4.32),(x+.045,5.3,5.40)))
    return result

def trigger():return [box((-1.48,2.42,.32),(1.48,5.38,.48),'CargoLift')]
