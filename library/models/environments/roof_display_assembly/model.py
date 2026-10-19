"""Static twin roof displays. Run from library with headless Blender 5.2.

Metres; ceiling mounting plane z=0, screens face -Y. No moving actions.
Manufactured parts meet at shared seats; unions remove casting interiors.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Screen': 'Emissive',
    'M_Secondary': 'Metallic',
}
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import light_common as common
kit = common.kit
ROOT = common.ROOT
NAME = HERE.name
TITLE = 'RoofDisplayAssembly'
SCREEN = 'M_Screen'
GLASS = 'M_Glass'
CENTRES = (-.35, .35)
emit, block, rod, loft = common.emit, common.block, common.rod, common.loft


def shift(bm, at):
    for v in bm.verts:
        v.co += Vector(at)
    return bm


def ceiling(k):
    plate = loft([(1.46,.38,.025,-.025),(1.46,.38,.025,-.007),
                  (1.446,.366,.021,0)])
    emit(k,plate,kit.SEC,'ceiling anchor plate')
    for x in (-.62,0,.62):
        for y in (-.14,.14):
            with k.frame(common.frame((x,y,-.025),(0,0,-1),(0,-1,0))):
                common.bolt(k,0,0,0,'ceiling anchor',.008)
    # Welded rail and downstands: broad flat ends at the anchor underside.
    rail = block((-.69,-.075,-.385),(.69,.075,-.275))
    supports = [block((x-.040,-.060,-.300),(x+.040,.060,-.025))
                for x in (-.50,.50)]
    rail = kit.machine(rail,union=supports,
        boxes=[((0,-.074,-.330),(1.26,.018,.018))])
    emit(k,rail,kit.FRM,'welded service rail and downstands')
    # Thin rail fascia sits exactly in the routed channel, without overlays.
    emit(k,block((-.63,-.083,-.339),(.63,-.065,-.321)),kit.SEC,'rail recessed fascia')
    for x in (-.50,.50):
        for z in (-.09,-.22):
            with k.frame(common.frame((x,-.060,z),(0,-1,0),(0,0,1))):
                common.bolt(k,0,0,0,'downstand fixing',.007)


def hanger(k,x):
    # Rail-clamped fixed drop to a bored fork; the two cheeks surround a tongue.
    fork = block((x-.050,-.060,-.475),(x+.050,.045,-.385))
    cheeks = [block((x+s*.055-.009,-.060,-.575),
                    (x+s*.055+.009,.010,-.455)) for s in (-1,1)]
    bore = ((x-.09,-.030,-.535),(x+.09,-.030,-.535),.012,12)
    fork = kit.machine(fork,union=cheeks,cuts=[bore])
    emit(k,fork,kit.FRM,'display clevis')
    # A cast tongue and shoulder foot: foot is flush on the housing's top flat.
    tongue = block((x-.035,-.057,-.600),(x+.035,-.003,-.505))
    foot = block((x-.090,-.105,-.605),(x+.090,-.025,-.587))
    tongue = kit.machine(tongue,union=[foot],cuts=[bore])
    emit(k,tongue,kit.PRI,'display mounting tongue and foot')
    emit(k,rod(*bore[:3],n=12),kit.JNT,'tilt through pin')
    for s in (-1,1):
        a,b=sorted((x+s*.09,x+s*.094))
        emit(k,rod((a,-.03,-.535),(b,-.03,-.535),.021,8),kit.JNT,'retaining tilt cap')
    # Fixed locking hardware on the drop; adjustment is manual, no motor needed.
    for dx in (-.026,.026):
        with k.frame(common.frame((x+dx,-.06,-.425),(0,-1,0),(0,0,1))):
            common.bolt(k,0,0,0,'clamp screw',.006)


def display(k,x):
    # Local coordinates: X across, Y up the screen, Z outward toward -Y.
    m = common.frame((x,-.025,-.82),(0,-1,0),(0,0,1))
    with k.frame(m):
        body = loft([(.616,.366,.025,0),(.660,.410,.031,.017),
                     (.68,.43,.034,.045),(.68,.43,.034,.096)])
        body = kit.machine(body,subtract=[(common.outline(.606,.356,.012,.145),(0,0,1),.15)])
        emit(k,body,kit.SEC,'lofted monitor rear casting')
        # Assign the whole manufactured bezel at emission, never by revisiting
        # accumulated world-space faces (which can recolour the other display).
        emit(k,common.ring(.68,.43,.034,.606,.356,.012,.096,.115),kit.PRI,'off-white removable bezel')
        emit(k,common.ring(.606,.356,.012,.590,.331875,.006,.070,.114),kit.FRM,'screen and glazing seal')
        emit(k,loft([(.590,.331875,.006,.070),(.590,.331875,.006,.101)]),kit.FRM,'LCD backer')
        # Inner glass face .111 is precisely 10 mm ahead of the LCD at .101.
        # A 2 mm pane is captive in the seal and recessed 2 mm below the bezel.
        emit(k,loft([(.590,.331875,.006,.111),(.590,.331875,.006,.113)]),GLASS,'10 percent opaque blue protective pane')
        for dx in (-.318,.318):
            for dy in (-.170,.170):
                common.bolt(k,dx,dy,.115,'bezel captive screw',.005)
        # Back cover bolted on the planar rear flat, with fused cooling ribs.
        back = loft([(.49,.27,.023,-.008),(.51,.29,.025,-.004),(.51,.29,.025,0)])
        fins=[block((dx-.003,-.092,-.015),(dx+.003,.092,-.006))
              for dx in (-.16,-.12,-.08,-.04,0,.04,.08,.12,.16)]
        emit(k,kit.machine(back,union=fins),kit.FRM,'rear service cover and heatsink')
        for dx in (-.23,.23):
            for dy in (-.115,.115):
                with k.frame(common.frame((dx,dy,-.008),(0,0,-1),(0,1,0))):
                    common.bolt(k,0,0,0,'rear cover screw',.004)
        # Outside service grip, with both feet welded flush to the side flat.
        s=math.copysign(1,x)
        def grip_block(a,b,c,d):
            xa,xb=sorted((s*a,s*b))
            return block((xa,c,.055),(xb,d,.079))
        grip=grip_block(.369,.383,-.110,.110)
        grip=kit.machine(grip,union=[grip_block(.340,.375,dy-.012,dy+.012)
                                    for dy in (-.098,.098)])
        emit(k,grip,kit.JNT,'outer connected service grip')


def conduit(points,r=.006,n=8):
    """Constant-radius cable with tangent circular elbows and transported frames.

    Every straight run has rings normal to that run at BOTH ends. Averaging
    adjacent point directions across a long run made the former tube taper.
    Circular fillets instead keep each section's radius and its true tangent.
    """
    p=[Vector(v) for v in points]
    assert len(p)>=2 and r>0 and n>=6
    assert all((b-a).length>1e-7 for a,b in zip(p,p[1:]))
    sections=[(p[0],(p[1]-p[0]).normalized())]
    for i,at in enumerate(p[1:-1],1):
        incoming=at-p[i-1];outgoing=p[i+1]-at
        d0=incoming.normalized();d1=outgoing.normalized()
        angle=math.acos(max(-1,min(1,d0.dot(d1))))
        if angle<1e-5:
            sections.append((at,d0));continue
        assert angle<math.pi-1e-4,'Cable cannot reverse at one point'
        trim=min(3*r*math.tan(angle/2),incoming.length*.35,outgoing.length*.35)
        radius=trim/math.tan(angle/2)
        assert radius>r*1.05,'Cable bend radius must clear its own wall'
        start=at-d0*trim
        inward=(d1-d0*d0.dot(d1)).normalized()
        centre=start+inward*radius
        axis=d0.cross(d1).normalized()
        count=max(2,math.ceil(angle/math.radians(22.5)))
        for step in range(count+1):
            turn=Quaternion(axis,angle*step/count)
            sections.append((centre+turn@(-inward*radius),turn@d0))
    sections.append((p[-1],(p[-1]-p[-2]).normalized()))
    rings=[];previous=None;u=None
    for at,tangent in sections:
        if previous is None:
            reference=Vector((1,0,0)) if abs(tangent.x)<.9 else Vector((0,1,0))
            u=(reference-tangent*reference.dot(tangent)).normalized()
        else:
            u=previous.rotation_difference(tangent)@u
            u=(u-tangent*u.dot(tangent)).normalized()
        v=tangent.cross(u).normalized()
        ring=[at+r*(u*math.cos(a*2*math.pi/n)+v*math.sin(a*2*math.pi/n)) for a in range(n)]
        assert all(abs((q-at).length-r)<1e-7 and abs((q-at).dot(tangent))<1e-7 for q in ring)
        rings.append(ring);previous=tangent
    return kit.loft_rings(rings)


def cables(k,x):
    # Both cable ends are normal to real rail/cover seats, with metal glands.
    emit(k,rod((x-.11,.075,-.33),(x-.11,.091,-.33),.011,8),kit.JNT,'rail cable gland')
    emit(k,rod((x+.19,-.017,-.82),(x+.19,-.001,-.82),.011,8),kit.JNT,'display cable gland')
    points=[(x-.11,.091,-.33),(x-.11,.13,-.33),(x-.10,.17,-.37),
            (x-.06,.18,-.43),(x+.04,.18,-.46),(x+.15,.17,-.49),
            (x+.20,.16,-.55),(x+.20,.16,-.72),(x+.19,.12,-.79),
            (x+.19,.05,-.82),(x+.19,-.001,-.82)]
    emit(k,conduit(points),kit.FRM,'retained signal and power loom')


def telemetry():
    """Deterministic original service UI; no reference pixels are copied."""
    w,h=1024,576
    px=np.ones((h,w,4),dtype=np.float32);px[:,:,:3]=(.006,.018,.024)
    teal=(.05,.57,.62); dim=(.018,.12,.15); amber=(.62,.32,.055)
    def line(x0,y0,x1,y1,col,width=1):
        count=max(abs(x1-x0),abs(y1-y0),1)+1
        xs=np.linspace(x0,x1,count).astype(int);ys=np.linspace(y0,y1,count).astype(int)
        for d in range(-width+1,width):
            px[np.clip(ys+d,0,h-1),np.clip(xs,0,w-1),:3]=col
    def box(x0,y0,x1,y1,col):
        for a,b,c,d in ((x0,y0,x1,y0),(x1,y0,x1,y1),(x1,y1,x0,y1),(x0,y1,x0,y0)):
            line(a,b,c,d,col)
    for x0,y0,x1,y1 in ((24,24,490,272),(510,24,998,272),(24,294,330,550),(350,294,700,550),(720,294,998,550)):
        box(x0,y0,x1,y1,teal)
        for xx in range(x0+12,x1,30):line(xx,y0+38,xx,y1-10,dim)
        for yy in range(y0+38,y1,24):line(x0+10,yy,x1-10,yy,dim)
        for xx in range(x0+12,x1-20,19):line(xx,y0+14,xx+9,y0+14,teal,2)
    for panel,(x0,x1,y0) in enumerate(((35,478,150),(521,986,150),(362,688,415))):
        old=None
        for xx in range(x0,x1):
            yy=int(y0+35*math.sin(xx*.038+panel)+13*math.sin(xx*.11))
            if old:line(*old,xx,yy,teal,2)
            old=(xx,yy)
    for i in range(13):
        yy=330+i*15
        for j in range(7):
            xx=38+j*39
            line(xx,yy,xx+12+(i*7+j*11)%20,yy,teal if j%3 else amber,2)
    for rr in (26,48,67):
        old=None
        for t in range(129):
            a=t*math.pi/64;p=(int(854+rr*math.cos(a)),int(415+rr*math.sin(a)))
            if old:line(*old,*p,teal)
            old=p
    image=bpy.data.images.new(NAME+'_telemetry',width=w,height=h,alpha=True)
    image.pixels.foreach_set(px.reshape(-1));image.pack()
    image.filepath_raw=str(HERE/f'{NAME}_telemetry.png');image.file_format='PNG';image.save()
    mat=bpy.data.materials[SCREEN];nodes=mat.node_tree.nodes;bsdf=nodes.get('Principled BSDF')
    tex=nodes.new('ShaderNodeTexImage');tex.image=image
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Emission Color'])


def screens(rig):
    meshes=[]
    for index,x in enumerate(CENTRES):
        contour=common.outline(.590,.331875,.006,0)
        verts=[(x+dx,-.126,-.82+dz) for dx,dz,_ in contour]
        mesh=bpy.data.meshes.new('screen');mesh.from_pydata(verts,[],[list(range(len(verts)))])
        obj=bpy.data.objects.new('SK_RoofDisplayScreen'+str(index+1),mesh);bpy.context.scene.collection.objects.link(obj)
        mesh.materials.append(bpy.data.materials[SCREEN]);uv=mesh.uv_layers.new(name='ScreenUV')
        for loop,(dx,dz,_) in zip(uv.data,contour):loop.uv=(dx/.590+.5,dz/.331875+.5)
        obj.vertex_groups.new(name=ROOT).add(list(range(len(verts))),1,'REPLACE');kit.skin(obj,rig)
        meshes.append(obj)
    return meshes


def main():
    kit.NAME,kit.TITLE=NAME,TITLE
    kit.MATERIALS[SCREEN]=((.03,.4,.45),0,.24,1.4)
    kit.MATERIALS[GLASS]=((.025,.12,.38),0,.12,0)
    kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials();telemetry()
    glass=bpy.data.materials[GLASS];bsdf=glass.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Alpha'].default_value=.10;bsdf.inputs['IOR'].default_value=1.46
    glass.diffuse_color=(*glass.diffuse_color[:3],.10);glass.surface_render_method='BLENDED'
    glass.use_backface_culling=True
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);rig['preview_poses']=json.dumps({})
    k=kit.Kit();common.LABELS.clear();common.CORNER_STEPS=1
    ceiling(k)
    for x in CENTRES:hanger(k,x);display(k,x);cables(k,x)
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    body=k.to_object('SK_'+TITLE);kit.skin(body,rig)
    # Keep transparent panes separate from the opaque body's visibility audit.
    glazing=body.copy();glazing.data=body.data.copy();glazing.name='SK_RoofDisplayGlass'
    bpy.context.scene.collection.objects.link(glazing)
    glass_slot=kit.SLOTS.index(GLASS)
    for obj,keep in ((glazing,True),(body,False)):
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if (f.material_index==glass_slot)!=keep],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free()
    glazing.data.materials.clear();glazing.data.materials.append(glass)
    for p in glazing.data.polygons:p.material_index=0
    # The separate screen replaces the backer's front face. Keeping both would
    # introduce a coplanar overlap and a visible diagonal depth-buffer artifact.
    bm=bmesh.new();bm.from_mesh(body.data)
    backer_faces=[f for f in bm.faces if all(abs(v.co.y+.126)<1e-6 for v in f.verts)]
    assert backer_faces
    bmesh.ops.delete(bm,geom=backer_faces,context='FACES_ONLY')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(body.data);bm.free()
    objects=[rig,body,glazing,*screens(rig)]
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],[('fixed',{})],(-.73,-.19),(.73,.19),
                        common.frame((0,0,0),(0,0,-1),(0,-1,0)))
    kit.check_coplanar(body)
    tris=sum(kit.triangles(o) for o in objects if o.type=='MESH');assert tris<=5000,tris
    points=[v.co for o in objects if o.type=='MESH' for v in o.data.vertices]
    lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
    assert abs(hi[2])<1e-6 and not bpy.data.actions
    if '--draft' not in sys.argv:
        common.prepare_export(objects,HERE,NAME);kit.select_only(objects)
        bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
            object_types={'MESH','ARMATURE'},global_scale=1.,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
            use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
            primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
            bake_anim=False,path_mode='COPY',embed_textures=True)
        bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
            use_selection=True,export_yup=True,export_apply=False,export_skins=True,
            export_def_bones=True,export_animations=False,export_materials='EXPORT')
    report={'name':NAME,'static':True,'animations':[],'triangles':tris,'triangle_budget':5000,
        'meshes':{o.name:kit.triangles(o) for o in objects if o.type=='MESH'},
        'bounds_m':{'lo':lo,'hi':hi},'tensor_height_m':1.753,
        'materials':sorted({o.data.materials[p.material_index].name for o in objects if o.type=='MESH' for p in o.data.polygons}),
        'bones':[{'name':ROOT,'kind':'fixed','parent':None}],
        'placement':'Ceiling mounting face z=0; front -Y; up +Z; all geometry below mounting plane.',
        'screens':{'active_size_m':[.590,.331875],'aspect':16/9,'front':[0,-1,0],
                   'uv0':'0..1 left-to-right, bottom-to-top; original embedded telemetry; runtime replaceable',
                   'glass_opacity':.10,'glass_colour':'blue','glass_clearance_m':.010,'glass_thickness_m':.002},
        'checks':{'connected_parts':len(k.parts),'exact_solid_pairs':pairs,'no_solid_intersections':True,
                  'coplanar':True,'budget':True,'no_actions':True},
        'mechanics':'Welded rail/downstands; bored clevises and through pins; retaining caps; seated removable bezels; sealed LCDs; rear heatsinks; terminal-anchored cable looms.'}
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles; bounds {lo} .. {hi}; static',flush=True)


if __name__=='__main__':main()
