"""Static standing workstation. Headless Blender 5.2; library-only.

Metres, floor origin, screens forward -Y. Every manufactured solid is audited
before hidden faces are culled. No actions or motorised joints are authored.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
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
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import light_common as common
kit = common.kit
ROOT = common.ROOT
NAME, TITLE = 'workstation', 'Workstation'
PRI, SEC, FRM, JNT, EMI = kit.PRI, kit.SEC, kit.FRM, kit.JNT, kit.EMI
emit, block, rod, loft = common.emit, common.block, common.rod, common.loft
SCREENS = []
DECK_TOP = 1.04
WIDTH, DEPTH = 1.50, .80
SCREEN_RADIUS = 1.50
GLASS = 'M_Glass'


def sag(x, radius):
    return radius-math.sqrt(radius*radius-x*x) if radius else 0


def curved_parts(target, source, frame, radius, labels):
    """Section every manufactured solid before bending it along one radius."""
    inv=frame.inverted();faces=list(source.bm.faces);cursor=0
    for part,tag in zip(source.parts,labels):
        bm=bmesh.new()
        vertices=[bm.verts.new(inv@p) for p in part.verts]
        for indices,old in zip(part.faces,faces[cursor:cursor+len(part.faces)]):
            face=bm.faces.new([vertices[i] for i in indices]);face.material_index=old.material_index
        cursor+=len(part.faces)
        if radius:
            for x in [i*.08 for i in range(-6,7)]:
                bmesh.ops.bisect_plane(bm,geom=bm.verts[:]+bm.edges[:]+bm.faces[:],
                                      dist=1e-7,plane_co=(x,0,0),plane_no=(1,0,0))
        for v in bm.verts:
            v.co.z+=sag(v.co.x,radius);v.co=frame@v.co
        bmesh.ops.triangulate(bm,faces=bm.faces[:])
        mats=[f.material_index for f in bm.faces]
        bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:])
        assert all(e.is_manifold for e in bm.edges),tag
        made=target.emit(bm,ROOT,SEC,False,convex=False,exact=True)
        for face,mat in zip(made,mats):face.material_index=mat
        common.LABELS.append(tag)
    source.bm.free()


def moved(bm, at):
    for v in bm.verts:
        v.co += Vector(at)
    return bm


def casting(k, stations, mat, tag, at=(0, 0, 0), **cuts):
    emit(k, kit.machine(moved(loft(stations), at), **cuts), mat, tag)


def side_profile(x):
    # A continuous perimeter rail. The two matching internal triangular
    # regions define the diagonal web instead of unrelated cutout shapes.
    yz = [(-.32,.08),(.32,.08),(.34,.10),(.34,.925),
          (.315,.95),(-.315,.95),(-.34,.925),(-.34,.10)]
    return [(x,y,z) for y,z in yz]


def structure(k):
    for s in (-1,1):
        x = s*.64
        casting(k,[(.22,.80,.025,0),(.22,.80,.025,.018),
                   (.20,.78,.023,.065),(.16,.72,.02,.08)],FRM,'floor shoe',at=(x,0,0))
        # Section loft along X; carved lightening aperture leaves a closed frame.
        sections=[side_profile(x+d) for d in (-.072,-.058,.058,.072)]
        for ring,fac in zip(sections,(.97,1,1,.97)):
            for i,(xx,y,z) in enumerate(ring):
                ring[i]=(xx,y*fac,.515+(z-.515)*fac)
        # Flat bottom and top mating pads retained at z=.08 and .95.
        for ring in sections:
            for i,(xx,y,z) in enumerate(ring):
                if i in (0,1):ring[i]=(xx,y,.08)
                if i in (4,5):ring[i]=(xx,y,.95)
        # 100 mm fore/aft rails, 120 mm top/bottom rails. The two triangular
        # regions are related by a half turn about their common centre.
        lower=[(-.130,.200),(.220,.200),(.240,.220),(.240,.680),
               (.215,.680),(-.140,.230)]
        upper=[(-y,1.030-z) for y,z in lower]
        def distance(p,a,b):
            p,a,b=Vector(p),Vector(a),Vector(b)
            t=max(0,min(1,(p-a).dot(b-a)/(b-a).length_squared))
            return (p-a.lerp(b,t)).length
        web=min(distance(p,a,b) for p in lower for a,b in zip(upper,upper[1:]+upper[:1]))
        assert web>.11,web
        assert all(-.24000001<=y<=.24000001 and .19999999<=z<=.83000001 for y,z in lower+upper)
        hole=[(x,y,z) for y,z in lower]
        core=kit.machine(kit.loft_rings(sections),subtract=[(hole,(1,0,0),.30)])
        emit(k,core,SEC,'lofted pierced side casting')
        # White outer armour follows the exact side outline and aperture seat.
        face_x=x+s*.072
        panel=kit.prism_bm(side_profile(face_x+s*.006),.012,(1,0,0))
        hatch=[(face_x+s*.019,y,z) for y,z in upper]
        panel=kit.machine(panel,subtract=[(hole,(1,0,0),.30),
                                          (hatch,(1,0,0),.026)])
        # Fish-mouth against the existing loft so no solid interiors overlap.
        emit(k,common.trim_seats(panel,[k.parts[-1]]),PRI,'off-white side armour')
        inset=[(face_x+s*.009,y,z) for _,y,z in hatch]
        emit(k,kit.prism_bm(inset,.006,(1,0,0)),FRM,'flush upper service armour insert')
        for y,z in ((-.195,.775),(.065,.797),(-.195,.450)):
            with k.frame(common.frame((face_x+s*.012,y,z),(s,0,0),(0,0,1))):
                common.bolt(k,0,0,0,'service insert screw',.006)
        for y,z in ((.285,.87),(.28,.15),(-.245,.87),(-.255,.14)):
            with k.frame(common.frame((face_x+s*.012,y,z),(s,0,0),(0,0,1))):
                common.bolt(k,0,0,0,'armour captive screw',.007)
    # Rear equipment cabinet braces both side frames, leaving toe/knee space.
    cabinet=loft([(1.136,.16,.014,.14),(1.136,.16,.014,.17),
                  (1.136,.16,.014,.89),(1.136,.16,.014,.95)])
    moved(cabinet,(0,.25,0))
    cabinet=kit.machine(cabinet,boxes=[((0,.331,.54),(1.00,.024,.59)),
                                     ((0,.169,.32),(.88,.026,.22))])
    emit(k,cabinet,FRM,'rear welded equipment cabinet')
    emit(k,block((-.499,.319,.246),(.499,.333,.834)),SEC,'seated rear service hatch')
    emit(k,block((-.439,.156,.211),(.439,.182,.429)),SEC,'seated front intake cartridge')
    for x in (-.39,-.26,-.13,0,.13,.26,.39):
        # Dark grille bars terminate on the intake surface; no loose slats.
        emit(k,block((x-.025,.153,.235),(x+.025,.156,.405)),FRM,'intake grille rib')
    for x in (-.47,.47):
        for z in (.27,.81):
            with k.frame(common.frame((x,.333,z),(0,1,0),(0,0,1))):
                common.bolt(k,0,0,0,'service hatch screw',.006)


def deck(k):
    # Continuous lofted desk shroud with a recessed operator cassette.
    body=loft([(1.42,.73,.04,.95),(1.50,.80,.045,.975),
               (1.50,.80,.045,1.018),(1.456,.756,.038,DECK_TOP)])
    body=kit.machine(body,boxes=[((0,-.12,1.085),(1.16,.42,.14)),
                                 ((0,-.402,.991),(.76,.024,.016)),
                                 ((-.16,.14,1.046),(.75,.016,.026))])
    emit(k,body,SEC,'lofted console shroud')
    emit(k,block((-.38,-.400,.983),(.38,-.390,.999)),EMI,'recessed front status strip')
    emit(k,block((-.535,.132,1.033),(.215,.148,1.038)),JNT,'recessed cable raceway lid')
    for x in (-.49,.17):
        common.bolt(k,x,.14,1.038,'raceway cover screw',.004)
    # Control tray lands on the recess floor at 1.015, 1 mm assembly seam.
    casting(k,[(1.158,.418,.018,1.015),(1.158,.418,.018,1.038)],FRM,
            'seated operator tray',at=(0,-.12,0))
    for s in (-1,1):
        # Palm/edge guards seat on the uninterrupted flat of the shroud.
        casting(k,[(.070,.62,.016,1.040),(.070,.62,.016,1.052),
                   (.052,.60,.012,1.063)],PRI,'side edge guard',at=(s*.674,-.01,0))
        # Guard bottom shares the uninterrupted deck's top seating plane.


def controls(k):
    # 19 mm pitch keys, sealed rugged 60-key keyboard; all caps on a tray.
    casting(k,[(.412,.152,.010,1.038),(.412,.152,.010,1.047)],SEC,
            'keyboard cassette',at=(0,-.205,0))
    for row in range(4):
        for col in range(15):
            x=(col-7)*.026
            y=-.205+(row-1.5)*.032
            emit(k,block((x-.010,y-.012,1.047),(x+.010,y+.012,1.053)),JNT,'sealed key cap')
    for s in (-1,1):
        x=s*.455
        casting(k,[(.125,.15,.015,1.038),(.125,.15,.015,1.045)],SEC,
                'joystick mounting plate',at=(x,-.18,0))
        emit(k,rod((x,-.18,1.045),(x,-.18,1.054),.044,12),JNT,'joystick retainer')
        casting(k,[(.064,.064,.018,1.054),(.040,.040,.011,1.080),
                   (.022,.022,.007,1.095)],FRM,'sealed joystick boot',at=(x,-.18,0))
        emit(k,rod((x,-.18,1.095),(x,-.18,1.140),.009,8),JNT,'joystick stalk')
        emit(k,rod((x,-.18,1.140),(x,-.18,1.172),.018,10),FRM,'joystick grip')
        for y in (-.29,-.08):
            emit(k,rod((x,y,1.038),(x,y,1.045),.018,10),SEC,'rotary control base')
            emit(k,rod((x,y,1.045),(x,y,1.059),.014,10),JNT,'rotary control dial')
    for x in (-.20,-.10,.10,.20):
        emit(k,block((x-.027,.031,1.038),(x+.027,.044,1.041)),EMI,'tray indicator')


def monitor(target, at, w, h, n, tag, radius=0):
    """LCD .069, glass .079..081, recessed bezel .088; metres."""
    m=common.frame(at,n,(0,0,1))
    k=kit.Kit();label_start=len(common.LABELS)
    iw,ih=w-.046,h-.046
    with k.frame(m):
        casting(k,[(w-.025,h-.025,.016,0),(w,h,.02,.016),
                   (w,h,.02,.054)],SEC,tag+' lofted back shell',
                subtract=[(common.outline(iw,ih,.006,.10),(0,0,1),.10)],
                boxes=[((x,y,0),(w*.18,.010,.008)) for x in (-w*.30,w*.30)
                       for y in (-h*.25,-h*.18,-h*.11)])
        for x in (-w*.30,w*.30):
            for y in (-h*.25,-h*.18,-h*.11):
                emit(k,block((x-w*.09,y-.005,0),(x+w*.09,y+.005,.004)),FRM,tag+' recessed cooling vent')
        emit(k,common.ring(w,h,.02,iw,ih,.006,.054,.088),PRI,tag+' removable bezel')
        emit(k,common.ring(iw,ih,.006,iw-.004,ih-.004,.004,.050,.086),FRM,tag+' captive seal')
        casting(k,[(iw-.004,ih-.004,.004,.050),(iw-.004,ih-.004,.004,.069)],FRM,tag+' LCD backer')
        casting(k,[(iw-.004,ih-.004,.004,.079),(iw-.004,ih-.004,.004,.081)],GLASS,tag+' blue protective pane')
        for x in (-w/2+.013,w/2-.013):
            for y in (-h/2+.013,h/2-.013):
                common.bolt(k,x,y,.088,tag+' bezel screw',.004)
    labels=common.LABELS[label_start:];del common.LABELS[label_start:]
    curved_parts(target,k,m,radius,labels)
    SCREENS.append((m,iw-.004,ih-.004,.069,tag,radius))
    return m


def displays(k):
    # A fixed, welded box-section arm and broad bolted rear mounting plate.
    emit(k,rod((0,.29,DECK_TOP),(0,.29,1.060),.072,12),JNT,'main monitor foot')
    emit(k,rod((0,.29,1.060),(0,.29,1.115),.049,12),FRM,'main monitor pedestal')
    monitor(k,(0,.31,1.438),1.04,.438,(0,-1,0),'Main',SCREEN_RADIUS)
    saddle=block((-.075,.295,1.385),(.075,.405,1.491))
    emit(k,common.trim_seats(saddle,k.parts),FRM,'main curved VESA saddle')
    for x in (-.058,.058):
        for z in (1.405,1.472):
            with k.frame(common.frame((x,.405,z),(0,1,0),(0,0,1))):
                common.bolt(k,0,0,0,'main monitor mounting screw',.005)
    arm=kit.prism_bm([(0,.265,1.115),(0,.315,1.115),(0,.435,1.225),
                     (0,.435,1.475),(0,.385,1.475),(0,.385,1.245)],.075,(1,0,0))
    emit(k,common.trim_seats(arm,k.parts),SEC,'main monitor welded neck')
    # Local bracket on the tablet back, inclined toward its operator.
    at=(.515,.07,1.222)
    normal=(0,-math.cos(math.radians(28)),math.sin(math.radians(28)))
    m=monitor(k,at,.300,.224,normal,'Auxiliary')
    with k.frame(m):
        emit(k,block((-.04,-.034,-.023),(.04,.034,0)),FRM,'tablet back mounting pad')
    emit(k,rod((.515,.13,DECK_TOP),(.515,.13,1.066),.045,12),JNT,'tablet foot')
    bracket=kit.prism_bm([(.515,.106,1.066),(.515,.154,1.066),
                          (.515,.112,1.230),(.515,.064,1.230)],.052,(1,0,0))
    emit(k,common.trim_seats(bracket,k.parts),SEC,'tablet fixed gusset pedestal')
    # Power/data routing concealed in the hollow pedestals; service cable exits
    # rear cabinet in a strain relief and follows a retained rear U-loop.
    emit(k,rod((-.29,.333,.78),(-.29,.349,.78),.012,8),JNT,'cabinet cable gland')
    emit(k,rod((-.29,.40,.991),(-.29,.416,.991),.012,8),JNT,'deck cable gland')
    points=[(-.29,.349,.78),(-.29,.426,.78),(-.29,.450,.805),
            (-.29,.450,.967),(-.29,.426,.991),(-.29,.416,.991)]
    # Same transported closed conduit as the sibling display assembly.
    emit(k,display_common.conduit(points,.006,8),FRM,'rear service loom')


def screen_meshes(body,rig):
    result=[]
    for m,w,h,z,tag,radius in SCREENS:
        inv=m.inverted()
        bm=bmesh.new();bm.from_mesh(body.data)
        dead=[f for f in bm.faces if all(abs((inv@v.co).z-sag((inv@v.co).x,radius)-z)<2e-6 and
              abs((inv@v.co).x)<w/2+1e-6 and abs((inv@v.co).y)<h/2+1e-6 for v in f.verts)]
        assert dead,tag
        bmesh.ops.delete(bm,geom=dead,context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(body.data);bm.free()
        stations=[i*.08 for i in range(-6,7) if abs(i*.08)<w/2-.004] if radius else []
        xs=sorted(set([-w/2,-w/2+.004,w/2-.004,w/2]+stations))
        contour=[(x,y,z+sag(x,radius)) for x in xs
                 for y in (-(h/2-.004 if abs(x)==w/2 else h/2),
                             h/2-.004 if abs(x)==w/2 else h/2)]
        mesh=bpy.data.meshes.new('Display_'+tag)
        mesh.from_pydata([m@Vector(p) for p in contour],[],
                        [(i*2,i*2+2,i*2+3,i*2+1) for i in range(len(xs)-1)])
        mesh.update()
        obj=bpy.data.objects.new('SK_WorkstationScreen'+tag,mesh)
        bpy.context.scene.collection.objects.link(obj);mesh.materials.append(bpy.data.materials['M_Screen'])
        uv=mesh.uv_layers.new(name='ScreenUV')
        for poly in mesh.polygons:
            for index in poly.loop_indices:
                p=contour[mesh.loops[index].vertex_index];uv.data[index].uv=(p[0]/w+.5,p[1]/h+.5)
        assert mesh.polygons[0].normal.y<-.85
        obj.vertex_groups.new(name=ROOT).add(list(range(len(mesh.vertices))),1,'REPLACE')
        kit.skin(obj,rig);result.append(obj)
    return result


spec=importlib.util.spec_from_file_location('workstation_display_helpers',HERE.parent/'roof_display_assembly/model.py')
display_common=importlib.util.module_from_spec(spec);spec.loader.exec_module(display_common)


def main():
    kit.NAME,kit.TITLE=NAME,TITLE
    common.CORNER_STEPS=1;common.LABELS.clear();SCREENS.clear()
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
    display_common.HERE=HERE;display_common.NAME=NAME;display_common.telemetry()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[])
    rig['preview_poses']=json.dumps({})
    k=kit.Kit()
    for fn in (structure,deck,controls,displays):fn(k)
    pairs=common.exact_intersections(k)
    pending=set(range(1,len(k.parts)));connected={0}
    while pending:
        found={i for i in pending if any(k.parts[i].touches(k.parts[j]) for j in connected)}
        if not found:
            raise AssertionError(('disconnected parts',[common.LABELS[i] for i in sorted(pending)]))
        connected.update(found);pending-=found
    kit.check_connectivity(k,joints,[])
    body=k.to_object('SK_'+TITLE);kit.skin(body,rig)
    glazing=body.copy();glazing.data=body.data.copy();glazing.name='SK_WorkstationGlass'
    bpy.context.scene.collection.objects.link(glazing)
    glass_slot=kit.SLOTS.index(GLASS)
    for obj,keep in ((glazing,True),(body,False)):
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if (f.material_index==glass_slot)!=keep],context='FACES_ONLY')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(obj.data);bm.free()
    glazing.data.materials.clear();glazing.data.materials.append(glass)
    for p in glazing.data.polygons:p.material_index=0
    screens=screen_meshes(body,rig)
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],[('fixed',{})],(-.75,-.40),(.75,.40))
    kit.check_coplanar(body)
    objects=[rig,body,glazing,*screens]
    tris=sum(kit.triangles(o) for o in objects if o.type=='MESH')
    assert tris<=5000,tris
    assert not bpy.data.actions
    lo=[min(v.co[i] for o in objects if o.type=='MESH' for v in o.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for o in objects if o.type=='MESH' for v in o.data.vertices) for i in range(3)]
    assert abs(lo[2])<1e-6 and hi[2]<1.70
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
            'bounds_m':{'lo':lo,'hi':hi},'tensor_height_m':1.753,'control_height_m':1.053,
            'placement':'floor centre z=0; screens front -Y, up +Z',
            'main_display_radius_m':SCREEN_RADIUS,
            'glazing':{'screen_air_gap_m':.010,'pane_thickness_m':.002,'opacity':.10},
            'side_frame':{'fore_aft_rail_m':.10,'top_bottom_rail_m':.12,
                          'matching_triangular_regions':True,'minimum_diagonal_web_m':.11},
            'materials':sorted({o.data.materials[p.material_index].name for o in objects if o.type=='MESH' for p in o.data.polygons}),
            'bones':[{'name':ROOT,'kind':'fixed','parent':None}],
            'joints':[{'bone':ROOT,'type':'fixed','parent':None,'pivot':[0,0,0],'range':None}],
            'checks':{'connected_parts':len(k.parts),'exact_solid_pairs':pairs,'no_solid_intersections':True,
                      'coplanar':True,'screen_normals_front':True,'budget':True,'no_actions':True}}
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles; {len(k.parts)} connected parts; {lo} .. {hi}',flush=True)


if __name__=='__main__':main()
