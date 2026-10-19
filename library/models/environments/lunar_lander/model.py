"""Static KYLR lunar lander. Run from library with headless Blender 5.2.

5 x 5 m deployed footprint, 5 m high; metres, front -Y, floor-centred origin.
The shared prop kit supplies lofts, exact booleans, connectivity, hidden-face
culling and native material atlases. All hardware is parked and fixed to Root;
there are deliberately no animation actions or deployable mechanisms.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
    'M_Titanium': 'Metallic',
}
import importlib.util
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
NAME = HERE.name
TITLE = 'LunarLander'
MODELS = HERE.parents[1]
sys.path.insert(0, str(MODELS))
from material_uv import prepare_export

spec = importlib.util.spec_from_file_location('lander_prop_kit', MODELS / 'gameplay/item_table/model.py')
kit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = kit
spec.loader.exec_module(kit)
kit.NAME, kit.TITLE = NAME, TITLE
kit.MATERIALS.update({
    'M_Titanium': ((.29, .29, .30), 1., .45, 0.),
    'M_Bronze': ((.72, .46, .20), 1., .22, 0.),
    # Sealed optical glazing, opaque to avoid exposing an unmodelled interior.
    'M_Glass': ((.018, .065, .08), .35, .14, 0.),
})
kit.SLOTS = list(kit.MATERIALS)
ROOT = 'Root'
PRI, SEC, FRM, JNT, EMI = kit.PRI, kit.SEC, kit.FRM, kit.JNT, kit.EMI
TI, BRZ, GLASS = 'M_Titanium', 'M_Bronze', 'M_Glass'
N = 16
FOOT_XY = 2.15
TRI_BUDGET = 5000
FACET = math.cos(math.pi/N)
UPPER_PIN_R = 1.67
UPPER_PIN_Z = 2.12
JOINT_GAP = .222
UPPER_EAR_X = (JOINT_GAP+.045)/2
FOOT_GAP = .234
FOOT_EAR_X = (FOOT_GAP+.045)/2
EYE_WIDTH = .22
PIN_RADIUS = .039
BORE_RADIUS = .040
ROD_RADIUS = .060
SLEEVE_BORE = .074


def annular_panel(k, outer, inner, normal, depth, mat):
    """One continuous inset frame, not a plate stacked over another plate."""
    bm=bmesh.new()
    n=Vector(normal).normalized()*depth/2
    rings=[[bm.verts.new(Vector(p)+sign*n) for p in outline]
           for sign in (-1,1) for outline in (outer,inner)]
    a,b,c,d=rings
    for i in range(len(a)):
        j=(i+1)%len(a)
        for face in ((a[i],a[j],c[j],c[i]),(b[j],b[i],d[i],d[j]),
                     (c[i],c[j],d[j],d[i]),(a[j],a[i],b[i],b[j])):
            bm.faces.new(face)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    k.emit(bm,ROOT,mat,False,convex=False,exact=True)


def bearing_eye(k, centre, axis, radius, width, mat=TI, bore=BORE_RADIUS):
    """Machined rod-end tongue with an actual transverse bore."""
    c,n=Vector(centre),Vector(axis).normalized()
    basis=n.to_track_quat('Z','Y').to_matrix()
    outer=[c+basis@Vector((radius*math.cos(i*math.tau/8),radius*math.sin(i*math.tau/8),0)) for i in range(8)]
    inner=[c+basis@Vector((bore*math.cos(i*math.tau/8),bore*math.sin(i*math.tau/8),0)) for i in range(8)]
    annular_panel(k,outer,inner,n,width,mat)


def retained_pin(k, centre, axis, span, radius=PIN_RADIUS):
    """Through-shaft, flush underside of hex head and opposing retaining nut."""
    c,n=Vector(centre),Vector(axis).normalized()
    k.cyl(c-n*span/2,c+n*(span/2+.012),radius,ROOT,JNT,segs=8)
    for sign in (-1,1):
        k.cyl(c+n*sign*(span/2),c+n*sign*(span/2+.010),radius*1.33,ROOT,JNT,segs=6)


def ring(r, z, n=N):
    # Facets centred on cardinal directions: fittings land on flats.
    return [(r*math.cos((i+.5)*math.tau/n), r*math.sin((i+.5)*math.tau/n), z) for i in range(n)]


def drum(k, stations, mat, n=N):
    k.emit(kit.loft_rings([ring(r,z,n) for z,r in stations]), ROOT, mat, False)


def closed_ring(k, profile, mat, n=N):
    """Sweep a closed radius/height section; true open bore with a return wall."""
    bm = bmesh.new()
    rows = [[bm.verts.new(p) for p in ring(r,z,n)] for r,z in profile]
    for a,b in zip(rows, rows[1:]+rows[:1]):
        for i in range(n):
            bm.faces.new((a[i],a[(i+1)%n],b[(i+1)%n],b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    k.emit(bm, ROOT, mat, False, convex=False, exact=True)


def rect_ring(w, d, z, c=.05, x=0, y=0):
    return [(x+a,y+b,z) for a,b in
            [(-w+c,-d),(w-c,-d),(w,-d+c),(w,d-c),
             (w-c,d),(-w+c,d),(-w,d-c),(-w,-d+c)]]


def panel(k, outline, y, depth, mat):
    k.emit(kit.prism_bm([(x,y,z) for x,z in outline], depth, (0,1,0)), ROOT, mat, False)


def octagon(w,h,z,c=.06):
    return [(-w+c,z-h),(w-c,z-h),(w,z-h+c),(w,z+h-c),
            (w-c,z+h),(-w+c,z+h),(-w,z+h-c),(-w,z-h+c)]


def pin(k, at, axis, r=.055, length=.32, mat=JNT, n=8):
    p,a = Vector(at), Vector(axis)*length/2
    k.cyl(p-a,p+a,r,ROOT,mat,segs=n)


def bolt(k, at, normal=(0,-1,0), r=.022):
    p,n = Vector(at),Vector(normal)
    k.cyl(p-n*.004,p+n*.014,r,ROOT,JNT,segs=6)


def build_descent(k):
    body=kit.loft_rings([ring(r,z) for z,r in
        [(1.20,1.12),(1.28,1.43),(1.40,1.50),(1.44,1.50),(2.36,1.50),(2.50,1.38),(2.56,1.22)]])
    pockets=[]
    unions=[]
    cuts=[((0,0,1.38),(0,0,2.43),1.30,16)]
    for az in (0,90,180,270):
        m=Matrix.Rotation(math.radians(az),4,'Z')
        pts=[(x,1.38,z) for x,z in octagon(.40,.40,1.90,.10)]
        pockets.append(([m@Vector(p) for p in pts],m.to_3x3()@Vector((0,1,0)),.60))
        cuts.extend([(m@Vector((0,1.15,1.355)),m@Vector((0,1.15,1.43)),.111,8),
                     (m@Vector((0,1.15,2.42)),m@Vector((0,1.15,2.466)),.046,6)])
    for az in (45,135,225,315):
        m=Matrix.Rotation(math.radians(az),4,'Z')
        for x in (-UPPER_EAR_X,UPPER_EAR_X):
            outline=[(x,1.37,1.95),(x,1.64,1.98),(x,1.79,2.05),
                     (x,1.79,2.20),(x,1.64,2.28),(x,1.37,2.28)]
            bm=kit.prism_bm(outline,.045,(1,0,0))
            bmesh.ops.transform(bm,matrix=m,verts=bm.verts[:])
            unions.append(bm)
        cuts.append((m@Vector((-.25,UPPER_PIN_R,UPPER_PIN_Z)),
                     m@Vector((.25,UPPER_PIN_R,UPPER_PIN_Z)),BORE_RADIUS,8))
        # Separate, bored drag-stay anchor bosses fuse into the lower ring.
        for x in (-.34,.34):
            outline=[(x,1.19,1.27),(x,1.48,1.27),(x,1.54,1.35),
                     (x,1.49,1.43),(x,1.19,1.43)]
            bm=kit.prism_bm(outline,.055,(1,0,0))
            bmesh.ops.transform(bm,matrix=m,verts=bm.verts[:])
            unions.append(bm)
            cuts.append((m@Vector((x-.07,1.46,1.35)),m@Vector((x+.07,1.46,1.35)),.024,6))
    kit.carve(k,body,ROOT,PRI,subtract=pockets,union=unions,cuts=cuts)
    # Colour bands are surface regions of this one shell, not overlaid sleeves.
    for face in k.bm.faces:
        c=face.calc_center_median()
        if face.material_index==kit.SLOTS.index(PRI) and (c.z<1.44 or c.z>2.36):
            face.material_index=kit.SLOTS.index(SEC)
    for az in (0,90,180,270):
        with k.frame(Matrix.Rotation(math.radians(az),4,'Z')):
            tank=kit.loft_rings([[(x,y+1.15,z) for x,y,z in ring(r,z,8)]
                for z,r in [(1.43,.12),(1.54,.29),(2.15,.29),(2.30,.20),(2.34,.075)]])
            kit.carve(k,tank,ROOT,JNT,cuts=[((0,1.15,2.31),(0,1.15,2.36),.046,6)],inner=JNT)
            k.cyl((0,1.15,1.355),(0,1.15,1.43),.11,ROOT,FRM,segs=8)
            k.cyl((0,1.15,2.310),(0,1.15,2.466),.045,ROOT,BRZ,segs=6)
            with k.frame(Matrix.Translation((0,1.15,0))):
                closed_ring(k,[(.290,1.845),(.303,1.845),(.303,1.915),(.290,1.915)],SEC,8)
            for sign in (-1,1):
                k.cyl((sign*.29,1.15,1.88),(sign*.45,1.25,1.88),.025,ROOT,TI,segs=6)


def window_plane(x,z,offset=0):
    centre=4.14
    radius=1.22+(centre-4.00)*(1.03-1.22)/.36
    slope=(1.22-1.03)/.36*FACET
    normal=Vector((0,-1,slope)).normalized()
    return Vector((x,-radius*FACET+slope*z,centre+z))+normal*offset


def build_cabin(k):
    hull=kit.loft_rings([ring(r,z) for z,r in
        [(2.56,1.22),(2.80,1.29),(3.76,1.29),(4.00,1.22),
         (4.36,1.03),(4.50,.76),(4.56,.52)]])
    # The airlock's planar seat is integral to the lofted hull. A broad flat
    # plate cannot sit flush across three curved facets without this fairing.
    fairing=kit.prism_bm([(x,-1.24,z) for x,z in octagon(.54,.56,3.23,.16)],.16,(0,1,0))
    hatch=octagon(.465,.495,3.23,.13)
    cuts=[([(x,-1.3125,z) for x,z in hatch],(0,1,0),.075)]
    normal=Vector((0,-1,(1.22-1.03)/.36*FACET)).normalized()
    for az in (-22.5,0,22.5):
        m=Matrix.Rotation(math.radians(az),4,'Z')
        cuts.append(([m@window_plane(x,z) for x,z in octagon(.207,.132,0,.03)],
                     m.to_3x3()@normal,.075))
    for az in (-90,90):
        m=Matrix.Rotation(math.radians(az),4,'Z')
        cuts.append(([m@Vector((x,-1.29*FACET,z)) for x,z in octagon(.227,.427,3.27,.045)],
                     m.to_3x3()@Vector((0,-1,0)),.075))
    m=Matrix.Rotation(math.pi,4,'Z')
    cuts.append(([m@Vector((x,-1.29*FACET,z)) for x,z in octagon(.227,.307,3.15,.05)],(0,1,0),.075))
    kit.carve(k,hull,ROOT,PRI,subtract=cuts,union=[fairing])
    annular_panel(k,[(x,-1.30,z) for x,z in octagon(.465,.495,3.23,.13)],
                  [(x,-1.30,z) for x,z in octagon(.405,.435,3.23,.10)],(0,1,0),.04,SEC)
    panel(k,octagon(.403,.433,3.23,.10),-1.295,.030,PRI)
    # The 2 mm seal reveal separates the pressure door and its recessed jamb.
    annular_panel(k,[(x,-1.2775,z) for x,z in octagon(.405,.435,3.23,.10)],
                  [(x,-1.2775,z) for x,z in octagon(.399,.429,3.23,.10)],(0,1,0),.005,FRM)
    for z in (2.96,3.48):
        with k.frame(Matrix.Translation((.435,-1.346,z))):
            for i in range(3):
                z0,z1=i*.044,i*.044+.042
                knuckle=kit.loft_rings([ring(.026,z0,6),ring(.026,z1,6)])
                if i==1:
                    # Stepped moving leaf seats on the door, clearing the jamb.
                    leaf=[(-.065,.036,z0+.021),(-.041,.036,z0+.021),
                          (.025,.011,z0+.021),(.025,-.003,z0+.021),
                          (-.002,-.015,z0+.021),(-.030,.011,z0+.021),
                          (-.065,.020,z0+.021)]
                    support=kit.prism_bm(leaf,.038,(0,0,1))
                else:
                    support=kit.loft_rings([rect_ring(.025,.006,z0+.002,.002,0,.020),
                                           rect_ring(.025,.006,z1-.002,.002,0,.020)])
                kit.carve(k,knuckle,ROOT,SEC if i==1 else JNT,union=[support],
                          cuts=[((0,0,z0-.01),(0,0,z1+.01),.011,6)],inner=JNT)
            k.cyl((0,0,-.006),(0,0,.138),.010,ROOT,JNT,segs=6)
    k.box((-.27,-1.325,3.23),(.07,.030,.13),ROOT,TI)
    k.box((-.21,-1.350,3.23),(.16,.020,.035),ROOT,JNT)
    for az in (-22.5,0,22.5):
        m=Matrix.Rotation(math.radians(az),4,'Z')
        annular_panel(k,[m@window_plane(x,z,-.012) for x,z in octagon(.207,.132,0,.03)],
                      [m@window_plane(x,z,-.012) for x,z in octagon(.161,.086,0,.022)],
                      m.to_3x3()@normal,.024,SEC)
        glass=[m@window_plane(x,z,-.011) for x,z in octagon(.160,.085,0,.022)]
        k.emit(kit.prism_bm(glass,.016,m.to_3x3()@normal),ROOT,GLASS,False)
    # Each radiator fits wholly on one flat, inside a machined seat.
    for az in (-90,90):
        with k.frame(Matrix.Rotation(math.radians(az),4,'Z')):
            face=-1.29*FACET
            panel(k,octagon(.224,.424,3.27,.045),face+.025,.025,SEC)
            for x in (-.135,0,.135):
                k.box((x,face+.00625,3.27),(.105,.0125,.74),ROOT,PRI)
    with k.frame(Matrix.Rotation(math.pi,4,'Z')):
        face=-1.29*FACET
        panel(k,octagon(.224,.304,3.15,.05),face+.01875,.0375,SEC)
        for x in (-.12,0,.12):
            k.box((x,face-.001,3.15),(.036,.004,.13),ROOT,FRM)
    drum(k,[(4.56,.49),(4.585,.49),(4.60,.40)],SEC,12)


def build_landing_gear(k):
    for sx,sy in ((1,1),(-1,1),(-1,-1),(1,-1)):
        foot=Vector((sx*FOOT_XY,sy*FOOT_XY,.240))
        d=Vector((sx,sy,0)).normalized()
        axis=Vector((d.y,-d.x,0))
        frame=Matrix((axis,d,Vector((0,0,1)))).transposed().to_4x4()
        k.emit(kit.loft_rings([rect_ring(.35,.35,0,.07,foot.x,foot.y),
                              rect_ring(.26,.26,.095,.055,foot.x,foot.y)]),ROOT,TI,False)
        # Foot fork is seated on the pad. Both cheeks have transverse bores;
        # the three rod-end eyes fit in the gap, with visible side clearances.
        with k.frame(Matrix.Translation((foot.x,foot.y,0))@frame):
            for x in (-FOOT_EAR_X,FOOT_EAR_X):
                outline=[(x,-.11,.095),(x,.11,.095),(x,.11,.265),
                         (x,.07,.315),(x,-.07,.315),(x,-.11,.265)]
                kit.carve(k,kit.prism_bm(outline,.045,(1,0,0)),ROOT,FRM,
                    cuts=[((x-.04,0,.24),(x+.04,0,.24),BORE_RADIUS,8)],inner=FRM)
        top=d*UPPER_PIN_R+Vector((0,0,UPPER_PIN_Z))
        length=(foot-top).length
        direction=(foot-top).normalized()
        bearing_eye(k,top,axis,.125,EYE_WIDTH,SEC)
        bearing_eye(k,foot,axis,.105,.13,TI)
        m=Matrix.Translation(top)@direction.to_track_quat('Z','Y').to_matrix().to_4x4()
        with k.frame(m):
            # Upper tube meets the eye's solid rim, clear of its transverse bore.
            # The recessed gland seats on a shoulder; it is not overlaid on the
            # full sleeve. Shaft overlap is wholly inside the open bore.
            end=length*.65
            closed_ring(k,[(.055,.10),(.13,.19),(.11,end-.075),
                           (.091,end-.075),(.091,end),
                           (SLEEVE_BORE,end),(SLEEVE_BORE,.19),(.04,.10)],SEC,6)
            closed_ring(k,[(.110,end-.075),(.110,end),
                           (.092,end),(.092,end-.075)],BRZ,6)
        k.cyl(top+direction*(length*.49),foot-direction*.15,ROD_RADIUS,ROOT,JNT,segs=8)
        k.cyl(foot-direction*.15,foot-direction*.074,ROD_RADIUS,ROOT,JNT,segs=8,r1=.035)
        retained_pin(k,top,axis,JOINT_GAP+2*.045)
        retained_pin(k,foot,axis,FOOT_GAP+2*.045)
        # Drag stays attach to actual chassis lugs and share the foot axle.
        # Their tongues occupy separate axial lanes alongside the main eye.
        for sign in (-1,1):
            start=d*1.46+axis*(sign*.394)+Vector((0,0,1.35))
            finish=foot+axis*(sign*.091)
            line=(finish-start).normalized()
            bearing_eye(k,start,axis,.060,.05,TI,bore=.025)
            bearing_eye(k,finish,axis,.067,.05,TI)
            k.cyl(start+line*.044,finish-line*.049,.024,ROOT,TI,segs=6)
            anchor=d*1.46+axis*(sign*(.34+.02575))+Vector((0,0,1.35))
            retained_pin(k,anchor,axis,.1065,radius=.024)


def build_engine(k):
    # Butt-joined thrust deck, injector flange and chamber. The nozzle's upper
    # rim meets the injector plane; the stainless exit lip meets its lower rim.
    drum(k,[(1.15,1.12),(1.20,1.12)],SEC,12)
    drum(k,[(1.12,.47),(1.15,.47)],FRM,12)
    drum(k,[(1.06,.31),(1.12,.31)],JNT,12)
    closed_ring(k,[(.31,1.06),(.28,.93),(.43,.55),(.61,.25),(.64,.20),
                   (.58,.20),(.38,.56),(.22,.93),(.23,1.06)],TI,12)
    closed_ring(k,[(.64,.18),(.64,.20),(.58,.20),(.58,.18)],JNT,12)


def build_access_and_comms(k):
    # The tread meets the bottom of the airlock fairing, with welded triangular
    # gussets underneath. Rails terminate in blind sockets in ground-level shoes.
    k.box((0,-1.525,2.70),(.94,.45,.08),ROOT,TI)
    for x in (-.35,.35):
        outline=[(x,-1.31,2.48),(x,-1.31,2.66),(x,-1.70,2.66)]
        k.emit(kit.prism_bm(outline,.035,(1,0,0)),ROOT,TI,False)
        bottom=Vector((x,-2.14,.082))
        top=Vector((x,-1.73,2.66))
        kit.carve(k,kit.loft_rings([rect_ring(.075,.115,0,.015,x,-2.14),
                                  rect_ring(.065,.105,.10,.015,x,-2.14)]),ROOT,TI,
            cuts=[(bottom, bottom+(top-bottom).normalized()*.05,.031,8)],inner=TI)
        k.cyl(bottom,top,.030,ROOT,JNT,segs=8)
        # A bent tube with surface-normal mounting feet, no projecting cut ends.
        rail_x=.425 if x>0 else -.425
        k.tube([(rail_x,-1.61,2.740),(rail_x,-1.61,3.37),(rail_x,-1.58,3.42),(rail_x,-1.32,3.42)],
               .020,ROOT,JNT,sides=6)
    for i in range(10):
        z=.25+i*.25
        y=-2.14+(z-.082)/(2.66-.082)*.41
        k.box((0,y,z),(.655,.075,.035),ROOT,SEC)
    # Both antenna bases seat on the flat crown, rather than penetrating its
    # shoulder. The dish's entire swept outline clears the crown at this pose.
    k.cyl((.16,.04,4.60),(.16,.04,4.625),.065,ROOT,SEC,segs=6)
    dish_normal=Vector((0,-math.sqrt(.5),math.sqrt(.5)))
    dish_seat=Vector((.16,.04,4.784))-dish_normal*.045
    basis=dish_normal.to_track_quat('Z','Y').to_matrix()
    post_rings=[[(.16+.028*math.cos(i*math.tau/6),.04+.028*math.sin(i*math.tau/6),z)
                 for i in range(6)] for z in (4.625,4.72)]
    post_rings.append([dish_seat+basis@Vector((.055*math.cos(i*math.tau/6),.055*math.sin(i*math.tau/6),0)) for i in range(6)])
    k.emit(kit.loft_rings(post_rings),ROOT,TI,False)
    with k.frame(Matrix.Translation((.16,.04,4.784))@Matrix.Rotation(math.radians(45),4,'X')):
        closed_ring(k,[(.030,-.045),(.060,-.045),(.060,-.030),(.11,-.015),(.22,.07),
                       (.22,.082),(.11,-.003),(.030,-.022)],PRI,8)
        for az in (0,120,240):
            a=math.radians(az)
            facet=round(az/45)*math.pi/4
            delta=a-facet
            r=.180
            effective=r*math.cos(delta)/math.cos(math.pi/8)
            height=-.003+(effective-.11)*.085/.11
            foot=Vector((r*math.cos(a),r*math.sin(a),height))
            normal=Vector((-.085/.11/math.cos(math.pi/8)*math.cos(facet),
                           -.085/.11/math.cos(math.pi/8)*math.sin(facet),1)).normalized()
            # Clip each welded feed strut's end to the reflector's actual flat.
            start=foot-normal*.020
            finish=Vector((0,0,.20))
            bm=bmesh.new()
            bmesh.ops.create_cone(bm,cap_ends=True,segments=6,radius1=.009,radius2=.009,depth=(finish-start).length)
            rot=(finish-start).to_track_quat('Z','Y').to_matrix()
            for v in bm.verts:v.co=rot@v.co+(start+finish)/2
            bmesh.ops.bisect_plane(bm,geom=bm.verts[:]+bm.edges[:]+bm.faces[:],
                                  plane_co=foot,plane_no=normal,clear_inner=True)
            bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0)
            bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
            k.emit(bm,ROOT,JNT,False)
        k.cyl((0,0,.190),(0,0,.215),.025,ROOT,FRM,segs=8)
    k.cyl((-.18,.05,4.60),(-.18,.05,4.625),.042,ROOT,SEC,segs=6)
    k.cyl((-.18,.05,4.625),(-.18,.05,5.0),.013,ROOT,JNT,segs=6)
    # RCS bases are entirely on a single constant-radius flat. No box emerges
    # from a curved shoulder and no nozzle is hidden in the cabin wall.
    for az in (45,135,225,315):
        with k.frame(Matrix.Rotation(math.radians(az),4,'Z')):
            seat=1.29*FACET
            k.box((0,seat+.050,3.56),(.20,.100,.14),ROOT,SEC)
            for sign in (-1,1):
                k.cyl((sign*.10,seat+.05,3.56),(sign*.19,seat+.05,3.56),
                      .027,ROOT,TI,segs=6,r1=.047)
                k.cyl((sign*.190,seat+.05,3.56),(sign*.192,seat+.05,3.56),
                      .032,ROOT,FRM,segs=6)
    # The lamp housing is seated on the actual shoulder plane. Its lens is in
    # a blind pocket, not laid over the housing's front face.
    z=3.86
    face=(1.29+(z-3.76)*(1.22-1.29)/.24)*FACET
    slope=(1.29-1.22)/.24*FACET
    normal=Vector((0,-1,slope)).normalized()
    def beacon_point(x,dz,offset):
        return Vector((x,-face+slope*dz,z+dz))+normal*offset
    case=[beacon_point(x,dz,.0075) for x,dz in [(-.05,-.022),(.05,-.022),(.05,.022),(-.05,.022)]]
    hole=[beacon_point(x,dz,.014) for x,dz in [(-.029,-.012),(.029,-.012),(.029,.012),(-.029,.012)]]
    kit.carve(k,kit.prism_bm(case,.015,normal),ROOT,FRM,
              subtract=[(hole,normal,.003)],inner=FRM)
    lens=[beacon_point(x,dz,.014) for x,dz in [(-.029,-.012),(.029,-.012),(.029,.012),(-.029,.012)]]
    k.emit(kit.prism_bm(lens,.003,normal),ROOT,EMI,False)


def export(objects, stem):
    prepare_export(objects,HERE,stem)
    kit.select_only(objects)
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{stem}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE'},global_scale=1.,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
        bake_anim=False,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{stem}.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_apply=False,export_skins=True,
        export_def_bones=True,export_animations=False,export_materials='EXPORT')


def check_coplanar(obj):
    """The shared prop audit, with a common projection axis for each pair.

    On diagonal planes equal X/Y normals can differ in their last float bit.
    Projecting each face on its own dominant axis compares unrelated coordinates
    and falsely reports opposite landing feet as overlapping. Both faces here
    use the first face's axis, and plane distances are also verified explicitly.
    """
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    pieces={}
    for face in bm.faces:
        if face in pieces:
            continue
        group=len(pieces)
        stack=[face]
        pieces[face]=group
        while stack:
            for edge in stack.pop().edges:
                for other in edge.link_faces:
                    if other not in pieces:
                        pieces[other]=group
                        stack.append(other)
    planes={}
    for face in bm.faces:
        if face.calc_area()>1e-7:
            n=face.normal
            key=(*[round(x,3) for x in n],round(n.dot(face.verts[0].co),4))
            planes.setdefault(key,[]).append(face)

    def inside(point,polygon):
        x,y=point
        result=False
        for (x0,y0),(x1,y1) in zip(polygon,polygon[1:]+polygon[:1]):
            if (y0>y)!=(y1>y) and x<x0+(x1-x0)*(y-y0)/(y1-y0):
                result=not result
        return result

    def samples(polygon):
        cx=sum(p[0] for p in polygon)/len(polygon)
        cy=sum(p[1] for p in polygon)/len(polygon)
        return [p for p in [(cx,cy)]+[(x+(cx-x)*.2,y+(cy-y)*.2) for x,y in polygon]
                if inside(p,polygon)]

    for faces in planes.values():
        for i,a in enumerate(faces):
            ax=max(range(3),key=lambda j:abs(a.normal[j]))
            u,v=[j for j in range(3) if j!=ax]
            pa=[(p.co[u],p.co[v]) for p in a.verts]
            for b in faces[i+1:]:
                if pieces[a]==pieces[b]:
                    continue
                if a.normal.dot(b.normal)<.999999 or any(
                    abs(a.normal.dot(p.co-a.verts[0].co))>1e-5 for p in b.verts):
                    continue
                pb=[(p.co[u],p.co[v]) for p in b.verts]
                if any(inside(p,pb) for p in samples(pa)) or any(inside(p,pa) for p in samples(pb)):
                    raise AssertionError(f'z-fighting at {tuple(a.calc_center_median())}')
    bm.free()


def check_interfaces():
    """Dimensional fits in the shared spec, in metres. No graph-only approval."""
    upper_side=(JOINT_GAP-EYE_WIDTH)/2
    foot_side=FOOT_GAP/2-(.091+.05/2)
    foot_between=.091-.05/2-.13/2
    assert .0009 <= upper_side <= .0011
    assert .0009 <= foot_side <= .0011
    assert .0009 <= foot_between <= .0011
    assert .0009 <= BORE_RADIUS-PIN_RADIUS <= .0011
    assert SLEEVE_BORE*math.cos(math.pi/6)-ROD_RADIUS >= .004
    # Neck end faces must be contained wholly in their eye's solid rim.
    assert math.hypot(.10,.055) < .125*math.cos(math.pi/8)
    assert math.hypot(.074,.035) < .105*math.cos(math.pi/8)
    assert math.hypot(.044,.024) < .060*math.cos(math.pi/8)
    assert math.hypot(.049,.024) < .067*math.cos(math.pi/8)
    assert 4.14-.132 > 4.00 and 4.14+.132 < 4.36
    top_window_radius=1.22+(4.272-4.00)*(1.03-1.22)/.36
    assert .207 < top_window_radius*math.sin(math.pi/N)
    assert .227 < 1.29*math.sin(math.pi/N)  # covers stay on one facet
    assert .425+.020*1.9 < .94/2  # whole grab-rail foot on tread
    fits={'upper_clevis_side_mm':upper_side*1000,
          'foot_clevis_side_mm':foot_side*1000,
          'foot_eye_spacing_mm':foot_between*1000,
          'pin_bore_radial_mm':(BORE_RADIUS-PIN_RADIUS)*1000,
          'shaft_bore_min_mm':(SLEEVE_BORE*math.cos(math.pi/6)-ROD_RADIUS)*1000,
          'window_recess_mm':3,'ladder_shoe_min_z_m':0}
    print(f'[{NAME}] mechanical seat and clearance checks passed: {fits}',flush=True)
    return fits


def split_assemblies(obj,rig):
    """Retain natural body/landing-gear assemblies after a combined visibility cull."""
    expected_material_faces={i:sum(p.material_index==i for p in obj.data.polygons) for i in range(len(obj.data.materials))}
    result=[]
    for value,tag in ((0,'Body'),(1,'Gear')):
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        layer=bm.faces.layers.int['Assembly']
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f[layer]!=value],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        mesh=bpy.data.meshes.new(f'SK_{TITLE}{tag}_Mesh')
        # Install slots before conversion so Blender retains face material indices.
        for material in obj.data.materials:
            mesh.materials.append(material)
        bm.to_mesh(mesh)
        bm.free()
        part=bpy.data.objects.new(f'SK_{TITLE}{tag}',mesh)
        bpy.context.scene.collection.objects.link(part)
        part.vertex_groups.new(name=ROOT).add(list(range(len(mesh.vertices))),1.0,'REPLACE')
        kit.skin(part,rig)
        mesh.set_sharp_from_angle(angle=kit.SHARP_ANGLE)
        result.append(part)
    assert sum(kit.triangles(p) for p in result)==kit.triangles(obj)
    actual_material_faces={i:sum(f.material_index==i for part in result for f in part.data.polygons) for i in expected_material_faces}
    assert actual_material_faces==expected_material_faces, (expected_material_faces,actual_material_faces)
    bpy.data.objects.remove(obj,do_unlink=True)
    return result


def main():
    kit.reset_scene()
    kit.build_materials()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints()
    rig=kit.build_rig(joints,[])
    k=kit.Kit()
    assembly=k.bm.faces.layers.int.new('Assembly')
    for builder in (build_descent,build_cabin,build_landing_gear,build_engine,build_access_and_comms):
        before=set(k.bm.faces)
        builder(k)
        for face in set(k.bm.faces)-before:
            face[assembly]=1 if builder==build_landing_gear else 0
    fits=check_interfaces()
    kit.check_connectivity(k,joints,[])
    print(f'[{NAME}] all {len(k.parts)} manufactured parts connected',flush=True)
    obj=k.to_object('SK_'+TITLE)
    kit.skin(obj,rig)
    early_lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    early_hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    assert all(abs(a-b)<1e-4 for a,b in zip(early_lo,[-2.5,-2.5,0])),early_lo
    assert all(abs(a-b)<1e-4 for a,b in zip(early_hi,[2.5,2.5,5])),early_hi
    if '--draft' in sys.argv:
        check_coplanar(obj)
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}_draft.blend'))
        print(f'[{NAME}] draft: {kit.triangles(obj)} triangles before visibility cull',flush=True)
        return

    # Free-standing floor prop: no cut-out; the ground lies under every foot.
    kit.cull_unseen(obj,rig,joints,[],[('parked',{})],(-2.5,-2.5),(2.5,2.5))
    check_coplanar(obj)
    tris=kit.triangles(obj)
    coords=[v.co for v in obj.data.vertices]
    lo=[min(v[i] for v in coords) for i in range(3)]
    hi=[max(v[i] for v in coords) for i in range(3)]
    assert all(abs(a-b)<1e-4 for a,b in zip(lo,[-2.5,-2.5,0])),lo
    assert all(abs(a-b)<1e-4 for a,b in zip(hi,[2.5,2.5,5])),hi
    assert not bpy.data.actions
    parts=split_assemblies(obj,rig)
    mesh_counts={p.name:kit.triangles(p) for p in parts}
    assert all(n<=TRI_BUDGET for n in mesh_counts.values()),mesh_counts
    export([rig,*parts],NAME)
    report={'name':NAME,'static':True,'animations':[], 'triangles':tris,
        'meshes':mesh_counts,'triangle_budget_per_mesh':TRI_BUDGET,'interface_fits':fits,
        'materials':list(kit.MATERIALS),'bounds_m':{'lo':lo,'hi':hi},
        'bones':[{'name':ROOT,'parent':None,'kind':'fixed','head':[0,0,0],'tail':[0,0,.1]}],
        'pistons':[], 'team_presets':{}, 'placement':'floor; front -Y; fixed deployed',
        'mechanics':'four crush struts and paired drag stays; central vacuum engine; sealed airlock; retained capsule tanks',
        'checks':{'connectivity':True,'coplanar':True,'envelope':True,'budget':True,'no_actions':True}}
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] build passed: {tris} triangles, 5 x 5 x 5 m, no animations',flush=True)


if __name__=='__main__':
    main()
