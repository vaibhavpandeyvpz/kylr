"""Static freestanding industrial terminal; scripted Blender 5.2, metres, front -Y.
Library-only. No animations. Manufactured solids are audited before culling.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Bronze': 'Metallic',
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
    'M_Light': 'Emissive',
    'M_Primary': 'Metallic',
    'M_Screen': 'Emissive',
    'M_Secondary': 'Metallic',
}
import importlib.util
import json
import math
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import light_common as common
spec=importlib.util.spec_from_file_location('terminal_monitor_helpers',HERE.parent/'workstation/model.py')
ws=importlib.util.module_from_spec(spec);spec.loader.exec_module(ws)
kit=common.kit
ROOT=common.ROOT
NAME,TITLE='terminal','Terminal'
PRI,SEC,FRM,JNT,EMI=kit.PRI,kit.SEC,kit.FRM,kit.JNT,kit.EMI
BRZ='M_Bronze'
GLASS=ws.GLASS
emit,block,rod,loft=common.emit,common.block,common.rod,common.loft
casting=ws.casting
SHELF_Y=-.08
SHELF_SEAT=(.54,.38,.03,1.01)


def structure(k):
    # A tapered floor flange with four captive foundation anchors.
    casting(k,[(.72,.64,.055,0),(.72,.64,.055,.025),
               (.66,.58,.045,.065),(.62,.54,.04,.080)],SEC,'floor anchor flange')
    for x in (-.27,.27):
        for y in (-.21,.21):common.bolt(k,x,y,.08,'foundation anchor',.009)
    # Deep load-bearing cabinet. Front and rear removable service seats are
    # machined into the shell, not laid on top of a solid duplicate volume.
    shell=loft([(.50,.34,.025,.08),(.54,.38,.03,.13),
                (.48,.32,.022,.24),(.48,.32,.022,.94),SHELF_SEAT])
    # Shared footprint with the control shelf: no rear ledge can emerge
    # beyond its underside chamfer. Only the upper cabinet section shifts.
    for v in shell.verts:
        if abs(v.co.z-SHELF_SEAT[3])<1e-6:v.co.y+=SHELF_Y
    shell=kit.machine(shell,boxes=[((0,-.160,.58),(.36,.024,.57)),
                                   ((0,.160,.56),(.36,.024,.62)),
                                   *[((side*.240,0,.58),(.024,.182,.382)) for side in (-1,1)]])
    emit(k,shell,FRM,'lofted equipment cabinet')
    with k.frame(common.frame((0,-.148,.58),(0,-1,0),(0,0,1))):
        casting(k,[(.358,.568,.025,0),(.358,.568,.025,.023)],PRI,'seated front service hatch')
    with k.frame(common.frame((0,.148,.56),(0,1,0),(0,0,1))):
        casting(k,[(.358,.618,.020,0),(.358,.618,.020,.023)],SEC,'seated rear service hatch')
    for side in (-1,1):
        for z in (.325,.835):
            with k.frame(common.frame((side*.145,-.171,z),(0,-1,0),(0,0,1))):
                common.bolt(k,0,0,0,'front hatch screw',.006)
        for z in (.280,.840):
            with k.frame(common.frame((side*.145,.171,z),(0,1,0),(0,0,1))):
                common.bolt(k,0,0,0,'rear hatch screw',.006)
    # Cooling cartridges sit in machined cabinet recesses. Their through
    # slots reveal the dark inset plenum backing without hidden machinery.
    # Small flange strips are functional grounding/retention plates.
    for side in (-1,1):
        x=side*.240
        with k.frame(common.frame((x,0,.58),(side,0,0),(0,0,1))):
            # Cartridge back seats on the exact machined recess floor.
            grille=loft([(.18,.38,.014,-.012),(.18,.38,.014,.013)])
            grille=kit.machine(grille,boxes=[((0,y,.018),(.13,.016,.060)) for y in (-.12,-.06,0,.06,.12)])
            emit(k,grille,SEC,'slotted side cooling cover')
    # Bronze latch plates sit on the flat front hatch, below the cooling zone.
    for x in (-.125,.125):
        with k.frame(common.frame((x,-.171,.41),(0,-1,0),(0,0,1))):
            casting(k,[(.035,.07,.005,0),(.035,.07,.005,.004)],BRZ,'service hatch latch')


def deck(k):
    # The control shelf transfers load to the full cabinet top face. No
    # disconnected lip or unsupported ends; one carved lofted casting.
    tray=loft([SHELF_SEAT,(.62,.54,.035,1.035),
               (.62,.54,.035,1.070),(.58,.50,.025,1.085)])
    ws.moved(tray,(0,SHELF_Y,0))
    tray=kit.machine(tray,boxes=[((0,-.14,1.106),(.48,.29,.064))])
    emit(k,tray,SEC,'lofted cantilever control shelf')
    casting(k,[(.478,.288,.012,1.074),(.478,.288,.012,1.083)],FRM,
            'seated sealed control cassette',at=(0,-.14,0))
    for x in (-.262,.262):
        common.bolt(k,x,-.27,1.085,'shelf retaining screw',.005)
    # Stainless palm guard terminates on the flat front shelf face.
    with k.frame(common.frame((0,-.35,1.049),(0,-1,0),(0,0,1))):
        handle=loft([(.30,.024,.004,0),(.30,.024,.004,.008)])
        emit(k,handle,JNT,'front palm guard')


def controls(k):
    for row in range(2):
        for col in range(6):
            x=-.15+col*.037;y=-.21+row*.040
            emit(k,rod((x,y,1.083),(x,y,1.089),.012,8),
                 BRZ if row else JNT,'sealed operator button')
    for x in (-.13,-.065,0,.065):
        emit(k,block((x-.018,-.061,1.083),(x+.018,-.049,1.086)),EMI,'status indicator')
    x,y=.185,-.25
    emit(k,rod((x,y,1.083),(x,y,1.091),.031,12),JNT,'joystick mounting collar')
    casting(k,[(.051,.051,.014,1.091),(.030,.030,.008,1.119),
               (.016,.016,.005,1.133)],FRM,'joystick sealed boot',at=(x,y,0))
    emit(k,rod((x,y,1.133),(x,y,1.18),.007,8),JNT,'joystick stainless stalk')
    emit(k,rod((x,y,1.18),(x,y,1.208),.013,10),FRM,'joystick grip')
    emit(k,rod((.16,-.07,1.083),(.16,-.07,1.088),.019,12),JNT,'dial mounting collar')
    emit(k,rod((.16,-.07,1.088),(.16,-.07,1.105),.015,10),SEC,'rotary selector')


def displays(k):
    # Inclined rugged monitor, fixed to a continuous structural spine.
    normal=(0,-math.cos(math.radians(15)),math.sin(math.radians(15)))
    monitor_frame=ws.monitor(k,(0,-.085,1.35),.50,.40,normal,'Main')
    # Upper spine and overhanging hood are one Boolean-unioned lofted shroud.
    spine=loft([(.50,.18,.022,1.085),(.50,.18,.022,1.68),
                (.56,.22,.026,1.77),(.52,.20,.024,1.85)])
    ws.moved(spine,(0,.095,0))
    hood=loft([(.56,.43,.03,1.72),(.60,.48,.035,1.77),
               (.58,.46,.033,1.825),(.52,.40,.028,1.85)])
    ws.moved(hood,(0,-.105,0))
    lamp_frame=common.frame((0,-.3325,1.745),(0,-1,-.5),(0,0,1))
    pocket=common.outline(.402,.032,.003,.008)
    pocket=[lamp_frame@Vector(p) for p in pocket]
    shroud=kit.machine(spine,union=[hood],
        boxes=[((0,.192,1.43),(.38,.016,.42))],
        subtract=[(pocket,lamp_frame.to_3x3()@Vector((0,0,1)),.040)])
    emit(k,common.trim_seats(shroud,k.parts),SEC,'fused spine and overhead hood')
    emit(k,block((-.189,.184,1.221),(.189,.198,1.639)),PRI,'upper rear access cover')
    for x in (-.16,.16):
        for z in (1.25,1.61):
            with k.frame(common.frame((x,.198,z),(0,1,0),(0,0,1))):
                common.bolt(k,0,0,0,'upper cover screw',.005)
    # The down-facing task lamp is recessed in the hood's angled front
    # lip. Its cutter, cassette and lens share one exact seating frame.
    with k.frame(lamp_frame):
        cassette=loft([(.40,.030,.003,-.012),(.40,.030,.003,0)])
        cassette=kit.machine(cassette,boxes=[((0,0,.001),(.36,.020,.006))])
        emit(k,cassette,FRM,'task lamp cassette')
        emit(k,block((-.18,-.010,-.002),(.18,.010,0)),'M_Light','warm task lamp lens')
    # A 100 mm VESA pattern on an inclined rear flange. The housing,
    # flange and weld seats share the monitor's exact authored frame.
    with k.frame(monitor_frame):
        casting(k,[(.14,.14,.012,-.008),(.14,.14,.012,0)],JNT,'inclined VESA rear flange')
        for x in (-.05,.05):
            for y in (-.05,.05):
                with k.frame(common.frame((x,y,-.008),(0,0,-1),(0,1,0))):
                    common.bolt(k,0,0,0,'VESA retaining screw',.005)
    with k.frame(common.frame((0,.005,1.35),(0,-1,0),(0,0,1))):
        casting(k,[(.17,.17,.012,0),(.17,.17,.012,.006)],SEC,'spine mounting flange')
        for x in (-.065,.065):
            for y in (-.065,.065):common.bolt(k,x,y,.006,'spine bracket screw',.005)
    # Two welded webs carry the display; their oblique ends are
    # trimmed against the inclined flange, their square ends against the
    # spine flange. A continuous load path replaces the former solid block.
    low=monitor_frame@Vector((0,-.050,-.006))
    high=monitor_frame@Vector((0,.050,-.006))
    seats=[p for p,label in zip(k.parts,common.LABELS)
           if label in ('inclined VESA rear flange','spine mounting flange')]
    for x in (-.031,.031):
        yz=[(low.y,low.z),(-.001,1.315),(-.001,1.385),(high.y,high.z)]
        web=kit.prism_bm([(x,y,z) for y,z in yz],.008,(1,0,0))
        web=common.trim_seats(web,seats)
        emit(k,web,SEC,'fitted welded monitor gusset')
    # Flush-sided armour strips on the straight spine flats, with real
    # fasteners and restrained bronze grip/latch accents.
    for side in (-1,1):
        with k.frame(common.frame((side*.25,.095,1.405),(side,0,0),(0,0,1))):
            panel=loft([(.15,.50,.018,0),(.15,.50,.018,.009)])
            panel=kit.machine(panel,boxes=[((0,y,.012),(.072,.018,.016)) for y in (-.02,.03,.08,.13)])
            emit(k,panel,PRI,'upper spine side armour')
            for y in (-.21,.21):common.bolt(k,0,y,.009,'spine armour fastener',.005)
            for y in (-.02,.03,.08,.13):
                emit(k,block((-.035,y-.008,.004),(.035,y+.008,.009)),BRZ,'seated spine vent cartridge')
    # The service interface above the LCD seats on the spine, safely below
    # the hood. Its recessed slot can accept a diagnostics connector.
    with k.frame(common.frame((0,.005,1.628),(0,-1,0),(0,0,1))):
        face=loft([(.39,.088,.012,0),(.39,.088,.012,.012)])
        face=kit.machine(face,boxes=[((0,0,.018),(.22,.016,.02))])
        emit(k,face,PRI,'upper diagnostic access plate')
        emit(k,block((-.109,-.007,.008),(.109,.007,.010)),FRM,'recessed diagnostic port')
        for x in (-.167,.167):common.bolt(k,x,0,.012,'diagnostic plate fastener',.005)
    # Vertical rear loom between two compression glands. Cable end tangents
    # are normal to their seats; each loop has a clamp on the rear hatch.
    x=-.105
    for z,y0 in ((.37,.171),(1.50,.198)):
        emit(k,rod((x,y0,z),(x,y0+.018,z),.012,8),JNT,'rear power and data gland')
    points=[(x,.189,.37),(x,.25,.37),(x,.28,.41),(x,.28,1.46),
            (x,.26,1.50),(x,.216,1.50)]
    emit(k,ws.display_common.conduit(points,.007,8),FRM,'retained rear service cable')
    for z in (.62,.81):
        bracket=block((x-.018,.171,z-.012),(x+.018,.29,z+.012))
        bracket=kit.machine(bracket,cuts=[((x,.28,z-.03),(x,.28,z+.03),.007,8)])
        emit(k,bracket,BRZ,'rear cable retaining clamp')


def main():
    kit.NAME,kit.TITLE=NAME,TITLE
    common.CORNER_STEPS=1;common.LABELS.clear();ws.SCREENS.clear()
    kit.MATERIALS[BRZ]=((.72,.46,.2),1,.32,0)
    kit.MATERIALS['M_Light']=((1,.65,.24),0,.4,2.5)
    kit.MATERIALS[EMI]=((.025,.55,.62),0,.4,1.5)
    kit.MATERIALS['M_Screen']=((.03,.4,.45),0,.28,1.2)
    kit.MATERIALS[GLASS]=((.025,.12,.38),0,.12,0)
    kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    glass=bpy.data.materials[GLASS];bsdf=glass.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Alpha'].default_value=.10;bsdf.inputs['IOR'].default_value=1.46
    glass.diffuse_color=(*glass.diffuse_color[:3],.10)
    glass.surface_render_method='BLENDED';glass.use_backface_culling=True
    # Reuse the original library service UI generator, saving to this asset.
    ws.display_common.HERE=HERE;ws.display_common.NAME=NAME;ws.display_common.telemetry()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[])
    rig['preview_poses']=json.dumps({})
    k=kit.Kit()
    for fn in (structure,deck,controls,displays):fn(k)
    seats=[]
    for label in ('lofted equipment cabinet','lofted cantilever control shelf'):
        part=next(p for p,tag in zip(k.parts,common.LABELS) if tag==label)
        seats.append({tuple(round(v[i],6) for i in (0,1)) for v in part.verts
                      if abs(v.z-SHELF_SEAT[3])<1e-6})
    assert seats[0]==seats[1] and len(seats[0])==8,'Cabinet/shelf seating outlines diverged'
    pairs=common.exact_intersections(k)
    pending=set(range(1,len(k.parts)));connected={0}
    while pending:
        found={i for i in pending if any(k.parts[i].touches(k.parts[j]) for j in connected)}
        if not found:
            raise AssertionError(('disconnected parts',[common.LABELS[i] for i in sorted(pending)]))
        connected.update(found);pending-=found
    kit.check_connectivity(k,joints,[])
    body=k.to_object('SK_'+TITLE);kit.skin(body,rig)
    glazing=body.copy();glazing.data=body.data.copy();glazing.name='SK_TerminalGlass'
    bpy.context.scene.collection.objects.link(glazing)
    glass_slot=kit.SLOTS.index(GLASS)
    for obj,keep in ((glazing,True),(body,False)):
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if (f.material_index==glass_slot)!=keep],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free()
    glazing.data.materials.clear();glazing.data.materials.append(glass)
    for p in glazing.data.polygons:p.material_index=0
    screens=ws.screen_meshes(body,rig)
    for o in screens:o.name=o.name.replace('Workstation','Terminal')
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],[('fixed',{})],(-.36,-.40),(.36,.32))
    kit.check_coplanar(body)
    objects=[rig,body,glazing,*screens]
    tris=sum(kit.triangles(o) for o in objects if o.type=='MESH')
    assert tris<=5000,tris
    assert not bpy.data.actions
    lo=[min(v.co[i] for o in objects if o.type=='MESH' for v in o.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for o in objects if o.type=='MESH' for v in o.data.vertices) for i in range(3)]
    assert abs(lo[2])<1e-6 and hi[2]<1.90
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
            'bounds_m':{'lo':lo,'hi':hi},'tensor_height_m':1.753,'control_height_m':1.089,
            'placement':'floor centre z=0; screens front -Y, up +Z',
            'screen_tilt_deg':15,'display_centre_height_m':1.35,
            'glazing':{'screen_air_gap_m':.010,'pane_thickness_m':.002,'opacity':.10},
            'materials':sorted({o.data.materials[p.material_index].name for o in objects if o.type=='MESH' for p in o.data.polygons}),
            'bones':[{'name':ROOT,'kind':'fixed','parent':None}],
            'joints':[{'bone':ROOT,'type':'fixed','parent':None,'pivot':[0,0,0],'range':None}],
            'checks':{'connected_parts':len(k.parts),'exact_solid_pairs':pairs,'no_solid_intersections':True,
                      'coplanar':True,'shared_shelf_seat':True,'screen_normals_front':True,'budget':True,'no_actions':True}}
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles; {len(k.parts)} connected parts; {lo} .. {hi}',flush=True)


if __name__=='__main__':main()
