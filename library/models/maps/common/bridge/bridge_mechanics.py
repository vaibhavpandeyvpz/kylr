"""Shared load frames, bolted splices and bored structural handrail clamps."""
import math
import sys
from pathlib import Path
import bmesh
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'platform'))
from platform_common import common,kit

# Shared platform-border paint, including native roughness/metallic settings.
METAL=common.SEC
POSTS=(-4.85,-3.55,-2.5,-1.45,-.15)


def transform(bm,matrix):
    for v in bm.verts:v.co=matrix@v.co
    return bm


def clipped(w,h,c,z0,z1):
    outline=[(-w/2+c,-h/2),(w/2-c,-h/2),(w/2,-h/2+c),(w/2,h/2-c),
             (w/2-c,h/2),(-w/2+c,h/2),(-w/2,h/2-c),(-w/2,-h/2+c)]
    return kit.prism_bm([(x,y,(z0+z1)/2) for x,y in outline],z1-z0,(0,0,1))


def cylinder(x0,x1,y,z,r,n=10):
    return kit.loft_rings([[(x,y+r*math.cos(math.pi/2+i*math.tau/n),
                            z+r*math.sin(math.pi/2+i*math.tau/n)) for i in range(n)] for x in (x0,x1)])


def rails_boxes(sign):
    x=sign*2.32
    return [((x-.045,-5,0),(x+.045,0,.16))]+[
        ((x-.04,y-.05,.16),(x+.04,y+.05,1.09)) for y in POSTS]+[
        ((x-.04,-5,z-.04),(x+.04,0,z+.04)) for z in (.34,.77,1.08)]


def fastener(k,x,y,z,label,r=.014):
    common.emit(k,common.rod((x,y,z),(x,y,z+.004),r,6),common.JNT,label)


def side_frame(k,s,map_detail=False):
    x=s*2.32
    core=kit.machine(common.block((x-.045,-5,0),(x+.045,0,.16)),union=[
        common.block((x-.04,y-.09,.16),(x+.04,y+.09,1.09)) for y in (-4.85,-.15)])
    common.emit(k,core,METAL,'shared toe frame and load-bearing railing / canopy end posts')
    if map_detail:return
    for y in (-4.85,-.15):
        for dy in (-.11,.11):fastener(k,x,y+dy,.16,'shared side-frame retention screw',r=.012)


def guard(k,s,map_detail=False):
    x=s*2.32;boxes=rails_boxes(s)
    if map_detail:
        core=kit.machine(common.block((x-.04,-2.55,.16),(x+.04,-2.45,1.12)),union=[common.block((x-.04,-4.76,z-.04),(x+.04,-.24,z+.04)) for z in (.34,.77,1.08)])
        common.emit(k,core,METAL,'continuous three-rail guard casting and central load stanchion')
        return
    # Fixed removable guard infill: the hardware retains the handrail.
    core=kit.machine(common.block(*boxes[2]),union=[common.block(*b) for b in boxes[3:5]])
    common.emit(k,core,METAL,'removable railing infill and three service stanchions')
    for z,r,material in ((.34,.023,common.SEC),(.77,.018,common.JNT),(1.08,.038,common.JNT)):
        tube=common.rod((x,-4.76,z),(x,-.24,z),r,10)
        tube=common.trim_seats(tube,[k.parts[0]])
        common.emit(k,tube,material,'retained round guard tie / stainless handrail')
    # Bored split saddles retain the removable handrail on its stanchions.
    for y in POSTS[1:-1]:
        saddle=kit.machine(common.block((x-.055,y-.09,1.045),(x+.055,y+.09,1.12)),
            cuts=[((x,y-.11,1.08),(x,y+.11,1.08),.038,10)])
        common.emit(k,saddle,common.SEC,'split handrail saddle anchored to load stanchion')
        for dy in (-.068,.068):
            common.emit(k,cylinder(x+s*.055,x+s*.062,y+dy,1.079,.012,6),common.JNT,'handrail saddle clamping screw')


def support_center(y,z):
    # Shared lower and upper columns use exactly the same centreline.
    return y


def roof_joint(k,s,y):
    x=s*2.32
    # Paired splice cheeks bridge the matching-width lower/upper post seam.
    # Two retained through-bolts transfer load into both column sections.
    for face in (-1,1):
        lo,hi=sorted((x+face*.04,x+face*.052))
        plate=kit.machine(common.block((lo,y-.08,.98),(hi,y+.08,1.20)),
            cuts=[((x-.065,y,z),(x+.065,y,z),.014,10) for z in (1.025,1.155)])
        common.emit(k,plate,common.SEC,'bolted column splice cheek bridging railing-to-roof joint')
    for z in (1.025,1.155):
        common.emit(k,cylinder(x-.056,x+.056,y,z,.0135,10),common.JNT,'retained column splice through-bolt')
        common.emit(k,cylinder(x+s*.056,x+s*.065,y,z,.022,6),METAL,'column splice hex retaining nut')
    # A top gusset carries the weather skin load onto the column, not a motor.
    gusset=kit.prism_bm([(x,y-.14,2.70),(x,y+.14,2.70),(x,y+.14,2.87),(x,y-.14,2.87)],.09,(1,0,0))
    gusset=common.trim_seats(gusset,[k.parts[0]])
    common.emit(k,gusset,common.SEC,'roof bearing saddle seated against column and weather skin')


def shield_frames():
    return [(s,y,common.frame((s*1.28,y,2.94+.13),(s*.12,0,1),(0,1,0)))
            for s in (-1,1) for y in (-4.04,-2.5,-.96)]


def shield_panel():
    def outline(w,h,c,z):
        return [(-w/2+c,-h/2,z),(w/2-c,-h/2,z),(w/2,-h/2+c,z),(w/2,h/2-c,z),
                (w/2-c,h/2,z),(-w/2+c,h/2,z),(-w/2,h/2-c,z),(-w/2,-h/2+c,z)]
    return kit.loft_rings([outline(2.05,1.34,.20,0),outline(2.05,1.34,.20,.025),
                           outline(1.85,1.14,.15,.08)])


def canopy(k,profile_function,map_detail=False):
    shell_profile=[(-2.5,-2.5,2.84),(2.5,-2.5,2.84),
                   (2.5,-2.5,2.94),(-2.5,-2.5,2.94)]
    shell=kit.prism_bm(shell_profile,5,(0,1,0));supports=[];windows=[]
    for s in (-1,1):
        for y in (-4.85,-.15):
            supports.append(kit.prism_bm([(s*2.32,cy,z) for cy,z in profile_function(y)],.08,(1,0,0)))
            direction=1 if y<-2.5 else -1
            windows.append(([(s*2.32,support_center(y,z)+offset,z)
                             for z,offset in ((1.32,-.065),(1.32,.065),(2.69,.065),(2.69,-.065))],(1,0,0),.20))
    shell=kit.machine(shell,union=supports,subtract=[] if map_detail else windows)
    common.emit(k,shell,METAL,'continuous load frame and thin weather canopy with exposed brace windows')
    if map_detail:return
    for s in (-1,1):
        for y in (-4.85,-.15):roof_joint(k,s,y)
    # Replaceable spaced impact shields: a sacrificial outer layer over the
    # continuous inner skin. Raised seats leave a real debris-fragment gap.
    for s,y,m in shield_frames():
        with k.frame(m):
            panel=kit.machine(shield_panel(),boxes=[((u,0,.083),(.11,.32,.046)) for u in (-.78,.78)])
            common.emit(k,panel,common.PRI,'faceted replaceable lunar debris shield')
            index=len(k.parts)-1
            for u in (-.78,.78):fastener(k,u,0,.060,'recessed impact shield captive hold-down',r=.022)
        for u in (-.78,.78):
            p=m@Vector((u,0,.012))
            base=2.94
            seat=common.block((p.x-.07,p.y-.09,base-.01),(p.x+.07,p.y+.09,p.z+.005))
            seat=common.trim_seats(seat,[k.parts[0],k.parts[index]])
            common.emit(k,seat,METAL,'spaced shield load seat anchored to continuous inner skin')
    # Recessed joint retainers protect the centre seam without exposed services.
    for y in (-4.04,-2.5,-.96):
        m=Matrix.Translation((0,y,0))
        lock=transform(clipped(.28,.72,.075,2.935,3.017),m)
        lock=common.trim_seats(lock,[k.parts[0]])
        common.emit(k,lock,common.SEC,'protected inner-skin joint retainer')
        fastener(k,0,y,3.017,'retainer captive roof attachment',r=.018)
    # The flat lower load plate provides a continuous longitudinal lamp seat.
