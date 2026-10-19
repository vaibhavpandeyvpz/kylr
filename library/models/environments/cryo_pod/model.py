"""Horizontal cryogenic pod, library only. Blender 5.2; metres, glass +Z.

A sealed static state: no animation. The shell, pressure seal and canopy share
exact mating outlines. Tensor is 1.753 m; the berth is 2.02 x 0.70 m.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Screen': 'Emissive',
    'M_Secondary': 'Metallic',
}
import importlib.util
import json
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Matrix, Vector
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import light_common as common
sys.path.insert(0, str(HERE.parents[1]/'gameplay/stasis_chamber'))
from model import pipe_mesh
_spec=importlib.util.spec_from_file_location('cryo_workstation_conduit',HERE.parent/'roof_display_assembly/model.py')
_workstation=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_workstation)
conduit=_workstation.conduit
kit, ROOT = common.kit, common.ROOT
NAME, TITLE = 'cryo_pod', 'CryoPod'
PRI, SEC, FRM, JNT, EMI = kit.PRI, kit.SEC, kit.FRM, kit.JNT, kit.EMI
BRZ, GLASS = 'M_Bronze', 'M_Glass'
emit, block, rod, loft = common.emit, common.block, common.rod, common.loft
DECK, CEILING = .46, 1.13

def move(bm, at):
    for v in bm.verts: v.co += Vector(at)
    return bm

def cast(k, stations, mat, label, at=(0,0,0), **cuts):
    emit(k, kit.machine(move(loft(stations),at), **cuts), mat,label)

def face(k,at,normal,w,h,depth,mat,label,**cuts):
    with k.frame(common.frame(at,normal,(0,0,1))):
        cast(k,[(w,h,min(.014,w*.18,h*.18),0),
                (w,h,min(.014,w*.18,h*.18),depth)],mat,label,**cuts)

def base(k):
    cast(k,[(.94,2.14,.12,0),(.94,2.14,.12,.035),
            (.88,2.08,.10,.075)],JNT,'anchored skid flange')
    # Two broad cradles land on the hull's 0.80 m-wide bottom flat.
    for y in (-.80,.80):
        cast(k,[(.80,.32,.035,.075),(.80,.32,.035,.15),
                (.80,.28,.025,.25)],FRM,'load bearing saddle',at=(0,y,0))
    for x in (-.42,.42):
        for y in (-.90,.90): common.bolt(k,x,y,.075,'skid anchor',.008)
    # A central equipment spine seats on the skid, clear of the cradles.
    cast(k,[(.53,1.08,.04,.075),(.58,1.08,.04,.10),
            (.58,1.08,.04,.215),(.53,1.08,.04,.25)],SEC,'coolant plant spine')
    for s in (-1,1):
        face(k,(s*.29,0,.16),(s,0,0),.76,.08,.012,FRM,
             'heat exchanger face', boxes=[((x,0,.015),(.016,.055,.030))
             for x in (-.30,-.24,-.18,-.12,-.06,0,.06,.12,.18,.24,.30)])

def enclosure(k):
    # Lofted monocoque tub, 70 mm floor, 80 mm upper rim. No stacked boxes.
    shell=loft([(.80,2.22,.22,.25),(.98,2.40,.30,.34),
                (1.06,2.50,.36,.48),(1.06,2.50,.36,.68),
                (1.00,2.44,.33,.76)])
    cavity=common.outline(.80,2.16,.27,.99)
    shell=kit.machine(shell,subtract=[(cavity,(0,0,1),1.34)],
        boxes=[((s*.53,0,.59),(.048,.74,.105)) for s in (-1,1)]+[((s*.53,y,.575),(.042,.40,.17)) for s in (-1,1) for y in (-.64,.64)])
    emit(k,shell,PRI,'lofted pressure tub')
    # Continuous gasket has the same inner edge as the canopy at its base.
    emit(k,common.ring(.80,2.16,.27,.776,2.136,.258,.735,.784),FRM,'pressure gasket')
    emit(k,common.ring(1.00,2.44,.33,.80,2.16,.27,.76,.79),SEC,'canopy retaining frame')
    # Double-wall lofted glazing. Hollow inner surface leaves the occupant
    # space clear; 12 mm radial and 14 mm crown wall thickness.
    outer=[(.776,2.136,.258,.784),(.776,2.136,.258,.835),
           (.71,2.04,.25,1.01),(.52,1.82,.22,1.12),(.30,1.54,.14,1.144)]
    inner=[(.752,2.112,.246,.70),(.752,2.112,.246,.835),
           (.686,2.016,.238,1.003),(.496,1.796,.208,1.107),(.276,1.516,.128,1.130)]
    bm=loft(outer)
    # Difference against the actual loft rather than a box approximating glass.
    cutter=loft(inner)
    from types import SimpleNamespace
    cutter.verts.index_update()
    part=SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],
                         faces=[[v.index for v in f.verts] for f in cutter.faces])
    bm=common.trim_seats(bm,[part]);cutter.free()
    # Shared dome split at the service boundary: head-side glass, foot-side
    # metal. The gasket band takes the exact same inner/outer loft surface.
    glass=bm.copy();hood=bm.copy();band=bm.copy();bm.free()
    emit(k,kit.machine(glass,boxes=[((0,2.54,1),(4,5,4))]),GLASS,'head half cyan canopy')
    hood=kit.machine(hood,boxes=[((0,-2.44,1),(4,5,4)),
                                 ((0,.35,1.144),(.22,.42,.018))])
    emit(k,hood,PRI,'foot half lofted insulated hood')
    band=kit.machine(band,boxes=[((0,2.56,1),(4,5,4)),((0,-2.46,1),(4,5,4))])
    emit(k,band,FRM,'canopy to hood pressure joint')
    cast(k,[(.218,.418,.025,1.135001),(.218,.418,.025,1.144)],SEC,
         'flush hood diagnostic hatch',at=(0,.35,0))
    for x in (-.085,.085):
        for y in (.18,.52):common.bolt(k,x,y,1.144,'hood hatch screw',.004)
    # A bed insert on the cavity floor, with an anchored head cushion.
    cast(k,[(.70,2.02,.19,.32),(.70,2.02,.19,.43)],SEC,'thermal berth deck')
    cast(k,[(.66,1.92,.18,.43),(.66,1.92,.18,DECK)],FRM,'insulated berth pad')
    cast(k,[(.36,.22,.06,DECK),(.34,.20,.06,.515)],SEC,'head support',at=(0,-.77,0))
    # Flush operator cassettes in pockets on the hull's uninterrupted side flats.
    for s in (-1,1):
        face(k,(s*.506,0,.59),(s,0,0),.738,.103,.022,FRM,'seated control cassette')
        face(k,(s*.528,-.12,.59),(s,0,0),.38,.048,.002,'M_Screen','sealed telemetry lens')
        for y in (-.33,.33):
            with k.frame(common.frame((s*.528,y,.59),(s,0,0),(0,0,1))):
                common.bolt(k,0,0,0,'cassette screw',.005)
    for s in (-1,1):
        for y in (-.64,.64):
            face(k,(s*.509,y,.575),(s,0,0),.398,.168,.021,SEC,'flush thermal service hatch',
                 boxes=[((a,0,.023),(.018,.10,.012)) for a in (-.12,-.04,.04,.12)])
            for a in (-.12,-.04,.04,.12):
                with k.frame(common.frame((s*.509,y,.575),(s,0,0),(0,0,1))):
                    emit(k,block((a-.009,-.05,.017),(a+.009,.05,.019)),FRM,'recessed thermal vent')
            with k.frame(common.frame((s*.53,y,.575),(s,0,0),(0,0,1))):
                for a in (-.17,.17):
                    for z in (0,):common.bolt(k,a,z,0,'service hatch captive screw',.004)
    # Rear bulkhead ports on the true flat end of the pressure tub. Bored
    # collars surround recessed plugs; the central cartridge is a vent stack.
    for x in (-.105,.105):
        with k.frame(common.frame((x,1.25,.575),(0,1,0),(0,0,1))):
            collar=rod((0,0,0),(0,0,.025),.041,12)
            collar=kit.machine(collar,cuts=[((0,0,-.01),(0,0,.04),.025,12)])
            emit(k,collar,JNT,'rear pressure service collar')
            emit(k,rod((0,0,0),(0,0,.019),.025,12),FRM,'recessed pressure service plug')
            emit(k,rod((0,0,.019),(0,0,.022),.014,6),BRZ,'service valve hex')
    face(k,(0,1.25,.575),(0,1,0),.065,.12,.016,SEC,'bulkhead purge grille',
         boxes=[((0,z,.020),(.04,.008,.014)) for z in (-.04,-.02,0,.02,.04)])
    for x in (-.435,.435):
        for y in (-.65,0,.65): common.bolt(k,x,y,.79,'frame captive screw',.006)

def hardware(k):
    # Longitudinal hinge pin: two fixed cheeks, central canopy knuckle and
    # pin bored through all three. All bearing feet sit on the rim's flat.
    for y in (-.57,.57):
        for d in (-.055,.055):
            bm=block((.400,y+d-.012,.79),(.471,y+d+.012,.845))
            bm=kit.machine(bm,cuts=[((.44,y+d-.020,.825),(.44,y+d+.020,.825),.010,12)])
            emit(k,bm,SEC,'hinge clevis foot')
        knuckle=block((.406,y-.035,.79),(.464,y+.035,.845))
        knuckle=kit.machine(knuckle,cuts=[((.44,y-.04,.825),(.44,y+.04,.825),.010,12)])
        emit(k,knuckle,JNT,'canopy hinge knuckle')
        emit(k,rod((.44,y-.070,.825),(.44,y+.070,.825),.010,12),BRZ,'retained hinge axle')
        for d in (-.073,.070):
            emit(k,rod((.44,y+d,.825),(.44,y+d+.003,.825),.017,10),JNT,'hinge pin retainer')
        # Compression lever and its stop land on the opposite flat rim.
        cast(k,[(.06,.13,.012,.79),(.06,.13,.012,.805)],FRM,'compression latch bed',at=(-.435,y,0))
        cast(k,[(.034,.085,.008,.805),(.034,.085,.008,.815)],JNT,'compression latch handle',at=(-.435,y,0))
    # Workstation-style retained U-looms and stasis coolant tubes: real ports
    # on the underside flat, never a cable running through the outer paint.
    for s in (-1,1):
        x=s*.335
        for y in (-.48,.48):
            emit(k,rod((x,y,.225),(x,y,.25),.024,10),JNT,'underside coolant gland')
        pts=[(x,-.48,.225),(x,-.48,.175),(x,-.43,.135),
             (x,.43,.135),(x,.48,.175),(x,.48,.225)]
        emit(k,pipe_mesh(pts,.012,8),JNT,'retained coolant return')
        for y in (-.27,.27):
            clamp=block((min(x,s*.29),y-.025,.113),(max(s*.36,s*.29),y+.025,.157)) if s>0 else block((-.36,y-.025,.113),(-.29,y+.025,.157))
            clamp=kit.machine(clamp,cuts=[((x,y-.032,.135),(x,y+.032,.135),.012,8)])
            emit(k,common.trim_seats(clamp,[p for p,tag in zip(k.parts,common.LABELS) if tag in ('heat exchanger face','coolant plant spine')]),FRM,'bored coolant saddle')
    # Workstation service loom, between two strain reliefs on the cabinet.
    for z in (.20,.09):
        emit(k,rod((.12,-.54,z),(.12,-.56,z),.012,8),JNT,'signal strain relief')
    emit(k,conduit([(.12,-.56,.20),(.12,-.60,.20),(.12,-.63,.175),
                     (.12,-.63,.12),(.12,-.60,.09),(.12,-.56,.09)],.006,8),FRM,'service signal loom')
def split_glass(body, rig):
    glazing=body.copy();glazing.data=body.data.copy();glazing.name='SK_'+TITLE+'Glass'
    bpy.context.scene.collection.objects.link(glazing)
    index=kit.SLOTS.index(GLASS)
    for obj, keep in ((glazing,True),(body,False)):
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if (f.material_index==index)!=keep],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free()
    glazing.data.materials.clear();glazing.data.materials.append(bpy.data.materials[GLASS])
    for p in glazing.data.polygons:p.material_index=0
    return glazing


def split_screens(body,rig):
    screen=body.copy();screen.data=body.data.copy();screen.name='SK_CryoPodScreen'
    bpy.context.scene.collection.objects.link(screen)
    index=kit.SLOTS.index('M_Screen')
    for obj,keep in ((screen,True),(body,False)):
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if (f.material_index==index)!=keep],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free()
    screen.data.materials.clear();screen.data.materials.append(bpy.data.materials['M_Screen'])
    uv=screen.data.uv_layers.new(name='ScreenUV')
    for poly in screen.data.polygons:
        poly.material_index=0
        for index in poly.loop_indices:
            p=screen.data.vertices[screen.data.loops[index].vertex_index].co
            m=common.frame((.53 if p.x>0 else -.53,-.12,.59),(1 if p.x>0 else -1,0,0),(0,0,1))
            q=m.inverted()@p
            uv.data[index].uv=(q.x/.38+.5,.60+q.y/.048*.22)
    return screen

def main():
    kit.NAME,kit.TITLE=NAME,TITLE
    common.CORNER_STEPS=2;common.LABELS.clear()
    kit.MATERIALS[BRZ]=((.72,.46,.2),1,.32,0)
    kit.MATERIALS[GLASS]=((.04,.52,.57),0,.16,0)
    kit.MATERIALS[EMI]=((.04,.72,.78),0,.35,2)
    kit.MATERIALS['M_Screen']=((.03,.4,.45),0,.28,1.2)
    kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    _workstation.HERE=HERE;_workstation.NAME=NAME;_workstation.telemetry()
    glass=bpy.data.materials[GLASS];bsdf=glass.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Alpha'].default_value=.18;bsdf.inputs['IOR'].default_value=1.46
    glass.diffuse_color=(*glass.diffuse_color[:3],.18)
    glass.surface_render_method='BLENDED';glass.use_backface_culling=True
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[])
    rig['preview_poses']=json.dumps({})
    k=kit.Kit()
    for fn in (base,enclosure,hardware):fn(k)
    pairs=common.exact_intersections(k)
    pending=set(range(1,len(k.parts)));connected={0}
    while pending:
        found={i for i in pending if any(k.parts[i].touches(k.parts[j]) for j in connected)}
        if not found:
            raise AssertionError(('disconnected parts',[common.LABELS[i] for i in sorted(pending)]))
        connected.update(found);pending-=found
    kit.check_connectivity(k,joints,[])
    body=k.to_object('SK_'+TITLE);kit.skin(body,rig)
    glazing=split_glass(body,rig)
    screen=split_screens(body,rig)
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],[('fixed',{})],(-.0001,-.0001),(.0001,.0001))
    kit.check_coplanar(body)
    objects=[rig,body,glazing,screen]
    tris=sum(kit.triangles(o) for o in (body,glazing,screen));assert tris<=5000,tris
    assert not bpy.data.actions
    points=[v.co for o in (body,glazing,screen) for v in o.data.vertices]
    lo=[min(p[i] for p in points) for i in range(3)]
    hi=[max(p[i] for p in points) for i in range(3)]
    assert abs(lo[2])<1e-6
    if '--draft' not in sys.argv:
        common.prepare_export(objects,HERE,NAME);kit.select_only(objects)
        bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
            object_types={'MESH','ARMATURE'},global_scale=1,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
            use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
            primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
            bake_anim=False,path_mode='COPY',embed_textures=True)
        bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
            use_selection=True,export_yup=True,export_apply=False,export_skins=True,
            export_def_bones=True,export_animations=False,export_materials='EXPORT')
    report={'name':NAME,'static':True,'animations':[],'triangles':tris,'triangle_budget':5000,
            'meshes':{o.name:kit.triangles(o) for o in (body,glazing,screen)},
            'bounds_m':{'lo':lo,'hi':hi},'tensor_height_m':1.753,
            'occupant':{'deck_m':DECK,'ceiling_m':CEILING,'berth_length_m':2.02,'berth_width_m':.70,'tensor_length_clearance_m':2.02-1.753},
            'placement':'floor centre z=0; long axis Y, head -Y; canopy opening +Z',
            'materials':sorted({o.data.materials[p.material_index].name for o in (body,glazing,screen) for p in o.data.polygons}),
            'bones':[{'name':ROOT,'kind':'fixed','parent':None}],
            'joints':[{'bone':ROOT,'type':'fixed','parent':None,'pivot':[0,0,0],'range':None}],
            'checks':{'connected_parts':len(k.parts),'exact_solid_pairs':pairs,
                      'no_solid_intersections':True,'coplanar':True,'canopy_double_wall':True,
                      'budget':True,'no_actions':True}}
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} tris; {len(k.parts)} connected parts; bounds {lo} .. {hi}',flush=True)


if __name__=='__main__':main()
