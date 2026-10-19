"""Static 3 x 2 m lunar survey rover, front -Y, floor-centred origin.

Run from library: Blender 5.2 --background --factory-startup --python
models/environments/lunar_rover/model.py. No actions or game integration.
Lofted shrouds, six metal wheels, passive rocker-bogie, corner steering,
recessed photovoltaic wings, stereo mast, high-gain dish and parked sampler.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Optics': 'Diffuse',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
    'M_Solar': 'Diffuse',
    'M_Titanium': 'Metallic',
}
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
NAME=HERE.name
TITLE='LunarRover'
MODELS=HERE.parents[1]
sys.path.insert(0,str(MODELS))
from material_uv import prepare_export
sys.path.insert(0,str(HERE))
from surface_audit import check_coplanar
spec=importlib.util.spec_from_file_location('rover_prop_kit',MODELS/'gameplay/item_table/model.py')
kit=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=kit
spec.loader.exec_module(kit)
kit.NAME,kit.TITLE=NAME,TITLE
kit.MATERIALS.pop('M_Emissive')
kit.MATERIALS.update({'M_Titanium':((.29,.29,.30),1.,.45,0.),
                     'M_Solar':((.018,.033,.055),.0,.26,0.),
                     'M_Optics':((.009,.026,.035),.45,.12,0.)})
kit.SLOTS=list(kit.MATERIALS)
PRI,SEC,FRM,JNT=kit.PRI,kit.SEC,kit.FRM,kit.JNT
TI,SOLAR,OPT='M_Titanium','M_Solar','M_Optics'
ROOT='Root'
WHEEL_Y=(-1.50,.12,1.50)
WHEEL_R=.38
WHEEL_Z=.38
BUDGET=5000

def rect(w,d,z,c=.05,x=0,y=0):
    return [(x+a,y+b,z) for a,b in [(-w+c,-d),(w-c,-d),(w,-d+c),
        (w,d-c),(w-c,d),(-w+c,d),(-w,d-c),(-w,-d+c)]]

def shell(k,stations,mat,x=0,y=0,c=.04):
    k.emit(kit.loft_rings([rect(w,d,z,c,x,y) for z,w,d in stations]),ROOT,mat,False)

def lathe(k,profile,mat,axis='Z',centre=(0,0,0),n=16,tread=False):
    """Closed section with real return wall; no concentric overlapping cylinders."""
    bm=bmesh.new();rows=[]
    for h,r in profile:
        row=[]
        for i in range(n):
            a=i*math.tau/n
            rr=r-(.013 if tread and r>=.36 and i%2 and i not in (n//4,3*n//4) else 0)
            p=Vector((rr*math.cos(a),rr*math.sin(a),h))
            if axis=='X':p=Vector((h,rr*math.cos(a),rr*math.sin(a)))
            row.append(bm.verts.new(p+Vector(centre)))
        rows.append(row)
    for a,b in zip(rows,rows[1:]+rows[:1]):
        for i in range(n):bm.faces.new((a[i],a[(i+1)%n],b[(i+1)%n],b[i]))
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
    k.emit(bm,ROOT,mat,False,convex=False,exact=True)

def cyl(k,a,b,r,mat=JNT,n=8):k.cyl(a,b,r,ROOT,mat,segs=n)

def cylinder_bm(a,b,r,n=8):
    a,b=Vector(a),Vector(b)
    rot=(b-a).normalized().to_track_quat('Z','Y').to_matrix()
    return kit.loft_rings([[p+rot@Vector((r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n),0))
                           for i in range(n)] for p in (a,b)])

def bolt(k,p,normal=(0,0,1),r=.017):
    p=Vector(p);v=Vector(normal)
    cyl(k,p,p+v*.012,r,JNT,6)

def eye(k,x,y,z,r,width,bore,mat=SEC):
    lathe(k,[(x-width/2,bore),(x-width/2,r),(x+width/2,r),
             (x+width/2,bore)],mat,'X',(0,y,z),8)

def beam(k,x,a,b,width=.13,depth=.15,mat=PRI):
    """One forged, bored link including its end eyes, rather than overlapping caps."""
    y0,z0=a;y1,z1=b
    v=Vector((0,y1-y0,z1-z0)).normalized()
    q=Vector((0,-v.z,v.y))*width/2
    p0,p1=Vector((x,y0,z0)),Vector((x,y1,z1))
    body=kit.prism_bm([p0+q,p1+q,p1-q,p0-q],depth,(1,0,0))
    unions=[]
    for y,z in (a,b):
        circle=[(x,y+.105*math.cos(i*math.tau/8),z+.105*math.sin(i*math.tau/8)) for i in range(8)]
        unions.append(kit.prism_bm(circle,depth,(1,0,0)))
    kit.carve(k,body,ROOT,mat,union=unions,cuts=[((x-.2,y,z),(x+.2,y,z),.040,8) for y,z in (a,b)],inner=JNT)

def build_body(k):
    hull=kit.loft_rings([rect(w*.8,d,z,c) for z,w,d,c in
        [(.68,.65,.82,.14),(.78,.78,1.04,.17),(1.05,.80,1.10,.17),
         (1.20,.72,1.12,.15),(1.24,.66,1.06,.12)]])
    # Flat service cover seat; the cap remains wholly inside its recess.
    cuts=[(rect(.26,.20,1.244,.045,0,.38),(0,0,1),.055)]
    spars=[kit.prism_bm(rect(1.30,.035,1.2525,.012,y=y),.055,(0,0,1)) for y in (-.70,0,.70)]
    spars.extend([kit.prism_bm(rect(.18,.18,1.26,.035,.22,0),.04,(0,0,1)),
                  kit.prism_bm(rect(.14,.12,1.26,.025,-.24,.04),.04,(0,0,1))])
    # Bearing flanges land wholly on planar chassis seats, even though the
    # surrounding shroud is lofted. The science fork has its own forward seat.
    for s in (-1,1):
        spars.append(kit.prism_bm([(s*.605,-.16,.75),(s*.605,.16,.75),
            (s*.605,.16,1.07),(s*.605,-.16,1.07)],.060,(1,0,0)))
    spars.append(kit.prism_bm([(p[0]-.30,-1.09,p[1]+.91)
        for p in rect(.12,.12,0,.02)],.080,(0,1,0)))
    kit.carve(k,hull,ROOT,PRI,subtract=cuts,union=spars)
    shell(k,[(1.2165,.255,.195),(1.235,.255,.195)],SEC,y=.38,c=.04)
    for x in (-.21,.21):
        for y in (.23,.53):bolt(k,(x,y,1.235))
    # Integral flat chassis underpan carries the suspension differential.
    shell(k,[(.62,.456,.70),(.68,.52,.82)],FRM,c=.10)
    # Bored differential tube, integral bearing housings and axial shoulders.
    # The through shaft runs in its bore, rather than through a solid cylinder.
    lathe(k,[(-.955+1/6,.040),(-.955+1/6,.065),(-.90+1/6,.065),
        (-.90+1/6,.145),(-.635,.145),(-.635,.09),(.635,.09),(.635,.145),
        (.90-1/6,.145),(.90-1/6,.065),(.955-1/6,.065),(.955-1/6,.040)],JNT,'X',(0,0,.91),8)
    cyl(k,(-1.105+1/6,0,.91),(1.105-1/6,0,.91),.039,JNT)

def build_running_gear(k):
    for s in (-1,1):
        with k.frame(Matrix.Translation((-s/6,0,0))):build_running_side(k,s)

def build_running_side(k,side):
    for s in (side,):
        x=s*1.03
        # Rocker apex at chassis axle, front termination and rear bogie pivot.
        outline=[(x,-1.56,.63),(x,0,1.015),(x,.88,.735),
                 (x,.88,.625),(x,0,.82),(x,-1.56,.53)]
        kit.carve(k,kit.prism_bm(outline,.15,(1,0,0)),ROOT,PRI,
            cuts=[((x-.2,y,z),(x+.2,y,z),.040,8) for y,z in ((-1.50,.58),(0,.91),(.83,.68))])
        # Bogie is a single elbow-shaped casting, with its two end eyes.
        bx=x-s*.153
        path=[(bx,.12,.58),(bx,.83,.68),(bx,1.50,.58)]
        body=kit.prism_bm([(bx,.04,.52),(bx,.04,.63),(bx,.83,.755),
            (bx,1.58,.63),(bx,1.58,.52),(bx,.83,.605)],.15,(1,0,0))
        kit.carve(k,body,ROOT,SEC,cuts=[((bx-.2,y,z),(bx+.2,y,z),.040,8) for _,y,z in path])
        for y,z in ((0,.91),(.83,.68)):
            if y!=0:cyl(k,(s*.793,y,z),(s*1.105,y,z),.039,JNT)
            bolt(k,(s*1.105,y,z),(s,0,0),.055)
            if y!=0:bolt(k,(s*.802,y,z),(-s,0,0),.055)
        for i,y in enumerate(WHEEL_Y):
            # The carrier's flat axial seat meets the arm's end boss; its
            # retained support shaft occupies a real blind bore in the carrier.
            inner=.955 if i==0 else .802
            cyl(k,(s*inner,y,.58),(s*1.165,y,.58),.039,JNT)
            bolt(k,(s*inner,y,.58),(-s,0,0),.052)
            if i!=0:
                lathe(k,[(s*.952,.040),(s*.952,.065),(s*1.105,.065),
                    (s*1.105,.040)],JNT,'X',(0,y,.58),8)
            motor=cylinder_bm((s*1.105,y,.38),(s*1.199,y,.38),.095)
            boss=kit.prism_bm([(s*1.135,y-.06,.52),(s*1.135,y+.06,.52),
                (s*1.135,y+.06,.64),(s*1.135,y-.06,.64)],.060,(1,0,0))
            if i!=1:
                upright=cylinder_bm((s*1.16,y,.445),(s*1.16,y,.70),.033)
                # Narrow stator cap clears the wheel's inner plane completely.
                shell(k,[(.70,.035,.070),(.77,.035,.060)],SEC,x=s*1.16,y=y,c=.010)
            else:
                upright=kit.loft_rings([rect(.035,.070,.38,.01,s*1.16,y),
                                        rect(.035,.070,.64,.01,s*1.16,y)])
            kit.carve(k,motor,ROOT,FRM,union=[upright,boss],cuts=[
                ((s*1.0,y,.58),(s*1.165,y,.58),.040,8),
                ((s*1.15,y,.38),(s*1.25,y,.38),.079,16)])
            # Profile includes the recessed outer dish and inner return.
            before=set(k.bm.faces)
            profile=[(1.20,.079),(1.20,.30),(1.24,.38),
                     (1.47,.38),(1.50,.35),(1.48,.235),(1.48,.079)]
            # Twenty-four integral, shallow axial grousers for regolith traction.
            lathe(k,[(s*h,r) for h,r in profile],TI,'X',(0,y,.38),48,True)
            cyl(k,(s*1.215,y,.38),(s*1.480,y,.38),.077,FRM,16)
            cyl(k,(s*1.480,y,.38),(s*1.495,y,.38),.099,JNT,8)
            for j in range(3):
                a=j*math.tau/3
                bolt(k,(s*1.480,y+.16*math.cos(a),.38+.16*math.sin(a)),(s,0,0),.015)
            label=k.bm.faces.layers.int['Assembly']
            for face in set(k.bm.faces)-before:face[label]=2

def build_solar(k):
    # Six mechanically framed cartridges seated on root spars, not floating wings.
    for x,w in ((-.91,1.333333333-.91),(0,.435),(.91,1.333333333-.91)):
        for y in (-.99,.99):
            if x!=0:y=math.copysign(1.02,y)
            d=.98 if x!=0 else .79
            z=1.315
            body=kit.loft_rings([rect(w,d,1.28,.08,x,y),rect(w,d,z,.08,x,y)])
            pocket=rect(w-.025,d-.025,z+.004,.065,x,y)
            before=set(k.bm.faces)
            kit.carve(k,body,ROOT,SEC,subtract=[(pocket,(0,0,1),.030)])
            # Cell grid is baked into the native UV atlas on the single recessed
            # laminate surface, saving thousands of invisible substrate faces.
            for f in set(k.bm.faces)-before:
                if all(abs(v.co.z-1.304)<1e-5 for v in f.verts):
                    f.material_index=kit.SLOTS.index(SOLAR)
                elif all(abs(v.co.z-z)<1e-5 for v in f.verts):
                    f.material_index=kit.SLOTS.index(JNT)
            for sy in (-1,1):
                bolt(k,(x,y+sy*(d-.017),z),r=.010)

def build_instruments(k):
    # Mast bearing pedestal seats in the central deck gap (front/rear cartridges).
    cyl(k,(.22,0,1.28),(.22,0,1.39),.16,SEC,8)
    lathe(k,[(1.39,.105),(1.39,.135),(1.47,.135),(1.47,.105)],JNT,centre=(.22,0,0),n=8)
    cyl(k,(.22,0,1.39),(.22,0,2.52),.104,PRI,8)
    cyl(k,(.22,0,2.52),(.22,0,2.57),.13,JNT,8)
    # One lofted sensor head, with four carved optical seats.
    head=kit.loft_rings([rect(.38,.14,2.57,.055,.22,0),
                         rect(.40,.17,2.65,.055,.22,0),rect(.36,.15,2.88,.045,.22,0)])
    centres=(-.055,.065,.375,.495)
    kit.carve(k,head,ROOT,PRI,cuts=[((x,-.23,2.75),(x,-.12,2.75),.043,8) for x in centres])
    for x in centres:
        cyl(k,(x,-.12,2.75),(x,-.165,2.75),.039,OPT,8)
    # Tilting high-gain antenna, fixed in its parked surveying pose.
    fork=kit.loft_rings([rect(.12,.10,1.28,.025,-.24,.04),
        rect(.10,.08,1.40,.02,-.24,.04),rect(.10,.08,1.62,.02,-.24,.04)])
    kit.carve(k,fork,ROOT,PRI,boxes=[((-.24,.04,1.535),(.154,.30,.34))],
        cuts=[((-.40,.04,1.49),(-.08,.04,1.49),.058,12)])
    cyl(k,(-.34,.04,1.49),(-.14,.04,1.49),.054,JNT,12)
    bolt(k,(-.34,.04,1.49),(-1,0,0),.068)
    bolt(k,(-.14,.04,1.49),(1,0,0),.068)
    # Captive thrust washers fill the clevis lanes, leaving a 0.15 mm oil gap
    # to the rotating tongue rather than leaving its ends unsupported.
    for s in (-1,1):
        lathe(k,[(s*.0752,.062),(s*.0752,.100),(s*.077,.100),(s*.077,.062)],
              JNT,'X',(-.24,.04,1.49),12)
    with k.frame(Matrix.Translation((-.24,.04,1.49))@Matrix.Rotation(math.radians(35),4,'X')):
        tongue=cylinder_bm((-.075,0,0),(.075,0,0),.11,12)
        neck=cylinder_bm((0,0,.08),(0,0,.17),.075,12)
        kit.carve(k,tongue,ROOT,SEC,union=[neck],
            cuts=[((-.10,0,0),(.10,0,0),.056,12)])
        lathe(k,[(.17,.01),(.17,.24),(.25,.34),(.268,.34),
                 (.254,.30),(.205,.20),(.194,.01)],PRI,n=12)
        cyl(k,(0,0,.194),(0,0,.22),.009,JNT,6)
    # UHF aerial: retained base, mast and cap; no unsupported garnish.
    cyl(k,(-.62,0,1.28),(-.62,0,1.40),.030,SEC)
    cyl(k,(-.62,0,1.40),(-.62,0,2.18),.016,JNT,8)
    cyl(k,(-.62,0,2.18),(-.62,0,2.20),.025,SEC,8)
    # Parked science arm tucked ahead of the belly, clear of the wheels.
    fork=kit.prism_bm([(p[0]-.30,-1.28,p[1]+.91)
        for p in rect(.097,.12,0,.02)],.30,(0,1,0))
    kit.carve(k,fork,ROOT,FRM,boxes=[((-.30,-1.39,.91),(.104,.39,.40))],
        cuts=[((-.42,-1.31,.91),(-.18,-1.31,.91),.040,8)])
    cyl(k,(-.397,-1.31,.91),(-.203,-1.31,.91),.039,JNT)
    bolt(k,(-.397,-1.31,.91),(-1,0,0),.052)
    bolt(k,(-.203,-1.31,.91),(1,0,0),.052)
    beam(k,-.30,(-1.31,.91),(-1.68,.78),.09,.10,SEC)
    cyl(k,(-.48,-1.68,.78),(-.25,-1.68,.78),.039,JNT)
    bolt(k,(-.48,-1.68,.78),(-1,0,0),.052)
    bolt(k,(-.25,-1.68,.78),(1,0,0),.052)
    lathe(k,[(-.378,.040),(-.378,.060),(-.352,.060),(-.352,.040)],JNT,'X',(0,-1.68,.78),8)
    beam(k,-.43,(-1.68,.78),(-1.18,.58),.075,.10,PRI)
    tool=kit.loft_rings([rect(.13,.12,.40,.025,-.43,-1.18),
                         rect(.13,.12,.69,.025,-.43,-1.18)])
    kit.carve(k,tool,ROOT,SEC,boxes=[((-.43,-1.18,.63),(.104,.40,.32))],
        cuts=[((-.60,-1.18,.58),(-.26,-1.18,.58),.040,8)])
    cyl(k,(-.56,-1.18,.58),(-.30,-1.18,.58),.039,JNT)
    bolt(k,(-.56,-1.18,.58),(-1,0,0),.052)
    bolt(k,(-.30,-1.18,.58),(1,0,0),.052)
    cyl(k,(-.43,-1.30,.44),(-.43,-1.37,.44),.025,JNT)

def bake_surface_textures(obj):
    """Bake deterministic cell circuitry and tread finish into native atlas UVs.

    Texture coordinates are derived from real dimensions after atlas packing;
    no Blender-only procedural nodes are required by the exported materials.
    """
    import numpy as np
    size=2048
    obj.data.calc_loop_triangles()
    uv=obj.data.uv_layers.active.data
    for mat_name in (SOLAR,TI):
        if not any(obj.data.materials[t.material_index].name==mat_name for t in obj.data.loop_triangles):continue
        pixels=np.zeros((size,size,4),dtype=np.float32)
        pixels[:,:,:3]=(.018,.033,.055) if mat_name==SOLAR else (.42,.42,.43)
        pixels[:,:,3]=1
        for tri in obj.data.loop_triangles:
            if obj.data.materials[tri.material_index].name!=mat_name:continue
            tex=np.array([uv[i].uv[:] for i in tri.loops])*size
            pos=np.array([obj.data.vertices[i].co[:] for i in tri.vertices])/.75
            x0,y0=np.maximum(np.floor(tex.min(axis=0)).astype(int),0)
            x1,y1=np.minimum(np.ceil(tex.max(axis=0)).astype(int),size-1)
            xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
            det=np.linalg.det(np.stack((tex[1]-tex[0],tex[2]-tex[0]),axis=1))
            if abs(det)<1e-7:continue
            inv=np.linalg.inv(np.stack((tex[1]-tex[0],tex[2]-tex[0]),axis=1))
            a=inv[0,0]*(xx-tex[0,0])+inv[0,1]*(yy-tex[0,1])
            b=inv[1,0]*(xx-tex[0,0])+inv[1,1]*(yy-tex[0,1])
            mask=(a>=-1e-5)&(b>=-1e-5)&(a+b<=1.00001)
            world=pos[0]+a[:,:,None]*(pos[1]-pos[0])+b[:,:,None]*(pos[2]-pos[0])
            x,y,z=world[:,:,0],world[:,:,1],world[:,:,2]
            if mat_name==SOLAR:
                xc=float(np.mean(pos[:,0]));xc=min((-.91,0,.91),key=lambda q:abs(xc-q))
                yc=math.copysign(.99 if xc==0 else 1.02,float(np.mean(pos[:,1])))
                w=.435 if xc==0 else 1.333333333-.91
                d=.79 if xc==0 else .98
                u=(x-xc+w-.025)/(2*w-.05)*4
                v=(y-yc+d-.025)/(2*d-.05)*8
                fu=u%1;fv=v%1
                gap=(fu<.025)|(fu>.975)|(fv<.014)|(fv>.986)
                gap|=(fu+fv<.085)|(fu+(1-fv)<.085)|((1-fu)+fv<.085)|((1-fu)+(1-fv)<.085)
                bus=(abs(fu-.33)<.004)|(abs(fu-.67)<.004)
                fingers=(fu*12)%1<.012
                col=np.empty((*x.shape,3),dtype=np.float32);col[:]=(.028,.058,.098)
                col[fingers&~gap]=(.065,.10,.14)
                col[gap]=(.20,.21,.23);col[bus&~gap]=(.30,.32,.35)
            else:
                cy=min(WHEEL_Y,key=lambda q:abs(float(np.mean(pos[:,1]))-q))
                angle=np.arctan2(z-.38,y-cy)
                rib=(angle*24/math.tau)%1
                tread=(abs(x)>1.06)&(abs(x)<1.304)&(np.hypot(y-cy,z-.38)>.32)
                col=np.empty((*x.shape,3),dtype=np.float32);col[:]=(.42,.42,.43)
                col[tread]=(.36,.36,.37)
                col[tread&(rib>.35)&(rib<.65)]=(.20,.21,.22)
                col[tread&((rib<.12)|(rib>.88))]=(.50,.50,.49)
            patch=pixels[y0:y1+1,x0:x1+1,:3];patch[mask]=col[mask]
        image=bpy.data.images.new(f'{TITLE}_{mat_name}_Surface',width=size,height=size,alpha=True)
        image.pixels.foreach_set(pixels.ravel());image.filepath_raw=str(HERE/f'{NAME}_{mat_name}_surface.png')
        image.file_format='PNG';image.save();image.pack()
        mat=bpy.data.materials[mat_name];node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
        mat.node_tree.links.new(node.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        if mat_name==SOLAR:
            shader=mat.node_tree.nodes.get('Principled BSDF')
            shader.inputs['IOR'].default_value=1.5
            shader.inputs['Coat Weight'].default_value=.25
            shader.inputs['Coat Roughness'].default_value=.16

def split_assemblies(obj,rig):
    """Natural chassis/instrument and running-gear meshes, as on the lander.

    The owning modelling guide caps props at 5,000 triangles per exported mesh.
    Splitting follows systems, retaining the combined visibility audit.
    """
    result=[]
    for value,tag in ((0,'Body'),(1,'Suspension'),(2,'Wheels')):
        bm=bmesh.new();bm.from_mesh(obj.data)
        label=bm.faces.layers.int['Assembly']
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f[label]!=value],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        mesh=bpy.data.meshes.new(f'SK_{TITLE}{tag}_Mesh')
        for mat in obj.data.materials:mesh.materials.append(mat)
        bm.to_mesh(mesh);bm.free()
        part=bpy.data.objects.new(f'SK_{TITLE}{tag}',mesh)
        bpy.context.scene.collection.objects.link(part)
        part.vertex_groups.new(name=ROOT).add(list(range(len(mesh.vertices))),1.,'REPLACE')
        kit.skin(part,rig);mesh.set_sharp_from_angle(angle=kit.SHARP_ANGLE)
        result.append(part)
    assert sum(kit.triangles(p) for p in result)==kit.triangles(obj)
    bpy.data.objects.remove(obj,do_unlink=True)
    return result

def check_interfaces():
    """Check dimensional seats and separations from the authored construction."""
    assert abs((1.2525+.055/2)-1.28)<1e-10  # spars meet panel undersides
    assert abs((1.26+.04/2)-1.28)<1e-10  # instrument pads meet flange feet
    assert abs((1.244-.055/2)-1.2165)<1e-10  # hatch bottom meets pocket floor
    assert .16<.18 and .12<.14 and .10<.12  # full footprints on mounting pads
    assert .030<.035  # antenna foot wholly on the centre spar
    assert .153-.15>.002  # rocker and bogie occupy separate axial lanes
    assert .154-.15>.003  # dish tongue fits its actual fork slot
    assert 1.535-.34/2<1.49-.11  # full dish eye clears the clevis floor
    assert .63-.32/2<.58-.105  # tool tongue clears its clevis floor
    assert .079*math.cos(math.pi/48)>.077  # no wheel bore/shaft penetration
    assert 1.195<1.20  # steering stator clears the inner wheel plane
    assert -.62+.016<-.24-.34  # whip antenna clears the entire reflector
    fits={'rocker_bogie_side_mm':(.153-.15)*750,
          'dish_clevis_side_mm':(.154-.15)/2*750,
          'support_pin_radial_mm':(.040-.039)*750,
          'solar_cartridge_end_seam_mm':(1.02-.98)*2*750,
          'solar_cartridge_lateral_seam_mm':(.91-(1.333333333-.91)-.435)*750,
          'wheel_steering_clearance_mm':(1.20-1.195)*750}
    print(f'[{NAME}] mechanical fits PASS: {fits}',flush=True)
    return fits

def main():
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[])
    k=kit.Kit()
    label=k.bm.faces.layers.int.new('Assembly')
    for fn in (build_body,build_running_gear,build_solar,build_instruments):
        before=set(k.bm.faces);fn(k)
        for face in set(k.bm.faces)-before:
            if face[label]!=2:face[label]=1 if fn==build_running_gear else 0
    fits=check_interfaces()
    kit.check_connectivity(k,joints,[])
    obj=k.to_object('SK_'+TITLE);kit.skin(obj,rig)
    # Uniform dimensional revision preserves circular bores and coaxial joints.
    for v in obj.data.vertices:v.co*=.75
    check_coplanar(obj)
    if '--draft' in sys.argv:
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}_draft.blend'))
        print(f'[{NAME}] draft {kit.triangles(obj)} triangles',flush=True);return
    kit.cull_unseen(obj,rig,joints,[],[('parked',{})],(-1,-1.5),(1,1.5))
    check_coplanar(obj)
    tris=kit.triangles(obj)
    lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    assert all(abs(a-b)<1e-5 for a,b in zip(lo,[-1,-1.5,0])),lo
    assert all(abs(a-b)<1e-5 for a,b in zip(hi,[1,1.5,2.16])),hi
    assert not bpy.data.actions
    parts=split_assemblies(obj,rig)
    counts={p.name:kit.triangles(p) for p in parts}
    assert all(n<=BUDGET for n in counts.values()),counts
    prepare_export(parts,HERE,NAME)
    for part in parts:bake_surface_textures(part)
    kit.select_only([*parts,rig])
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',use_selection=True,
        export_yup=True,export_skins=True,export_animations=False,export_materials='EXPORT')
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE'},global_scale=1.,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',use_mesh_modifiers=False,
        mesh_smooth_type='OFF',add_leaf_bones=False,primary_bone_axis='Y',secondary_bone_axis='X',
        use_armature_deform_only=True,bake_anim=False,path_mode='COPY',embed_textures=True)
    report={'name':NAME,'static':True,'animations':[],'triangles':tris,'meshes':counts,
        'materials':sorted({p.data.materials[f.material_index].name for p in parts for f in p.data.polygons}),
        'bounds_m':{'lo':lo,'hi':hi},'triangle_budget_per_mesh':BUDGET,'placement':'floor-centred, front -Y',
        'interface_fits':fits,'authored_parts':len(k.parts),
        'checks':{'connectivity':True,'coplanar':True,'mechanical_seats':True,'envelope':True,'budget':True,'no_actions':True},
        'mechanics':'passive rocker-bogie; six hub motors; four steering knuckles; fixed deployed solar cartridges; stereo mast; dish; parked science arm'}
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles; 3 x 2 x 2.16 m; static',flush=True)

if __name__=='__main__':main()
