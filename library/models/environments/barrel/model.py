"""Static 0.95 m industrial service barrel; metres, front -Y, floor origin.
Two stamped shells, mechanical gauge, protected drain, capped charge socket,
retained lid and lifting grips. No electronic screen, actions or game changes.
Run Blender 5.2 headless from library/. Script is the editable source.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Frame': 'Diffuse',
    'M_Glass': 'Glass',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
import bmesh
import bpy
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import light_common as common
kit,ROOT=common.kit,common.ROOT
PRI,SEC,FRM,JNT=kit.PRI,kit.SEC,kit.FRM,kit.JNT
GLASS='M_Glass'
NAME,TITLE='barrel','Barrel'
HEIGHT,RADIUS,SEGMENTS=.950,.300,32
HALF_FACET=math.pi/SEGMENTS
emit,block,rod,loft=common.emit,common.block,common.rod,common.loft
FRONT_DEPTH=.295

def polar(r,a,z):return (r*math.cos(a),r*math.sin(a),z)
def moved(bm,at):
    for v in bm.verts:v.co+=Vector(at)
    return bm
def transformed(bm,m):
    for v in bm.verts:v.co=m@v.co
    return bm
def drum(stations):
    return kit.loft_rings([[polar(r,-math.pi/2-HALF_FACET+j*math.tau/SEGMENTS,z)
                            for j in range(SEGMENTS)] for z,r in stations])
def sector(stations,first,last):
    angles=[-math.pi/2+j*HALF_FACET for j in range(first,last+1,2)]
    return kit.loft_rings([[polar(ro,a,z) for a in angles]+
                           [polar(ri,a,z) for a in reversed(angles)]
                          for z,ro,ri in stations])
def radial(a,r,z):
    return common.frame(polar(r,a,z),(math.cos(a),math.sin(a),0),(0,0,1))
def subtract_bmesh(body,cutter):
    cutter.verts.index_update()
    tool=SimpleNamespace(verts=[v.co.copy() for v in cutter.verts],
                         faces=[[v.index for v in f.verts] for f in cutter.faces])
    result=common.trim_seats(body,[tool]);cutter.free()
    return result
def socket(k,r,bottom,top,label):
    bm=kit.machine(rod((0,0,bottom),(0,0,top),r,8),
                   cuts=[((0,0,top-.0015),(0,0,top+.004),r*.45,6)])
    start=len(k.bm.faces);emit(k,bm,JNT,label);inverse=k.xf.inverted()
    for f in list(k.bm.faces)[start:]:
        c=inverse@f.calc_center_median()
        if math.hypot(c.x,c.y)<r*.52 and c.z<top-.0001:
            f.material_index=kit.SLOTS.index(FRM)

def structure(k):
    emit(k,drum([(0,.260),(.020,.285),(.035,.300),(.070,.300),
                  (.095,.282),(.120,.258)]),SEC,'bottom impact collar')
    core=drum([(.120,.250),(.170,.250),(.770,.250),(.820,.250)])
    # The service casting has a true flat; its mounts never sit on a curve.
    spine=transformed(loft([(.185,.660,.026,-.018),(.185,.660,.026,.012),
                            (.155,.610,.018,.045)]),radial(-math.pi/2,.250,.470))
    backrib=sector([(.120,.258,.245),(.170,.273,.245),
                    (.770,.273,.245),(.820,.258,.245)],31,33)
    core=kit.machine(core,union=[spine,backrib])
    bmesh.ops.triangulate(core,faces=core.faces[:])
    for radius,z in ((.046,.620),(.024,.320)):
        core=subtract_bmesh(core,transformed(rod((0,0,-.010),(0,0,.05),radius,24 if radius>.04 else 12),
                                             radial(-math.pi/2,FRONT_DEPTH,z)))
    ears=[block((x-.006,-.326,.746),(x+.006,-.282,.786)) for x in (-.023,.023)]
    core=kit.machine(core,union=ears,
                     cuts=[((-.040,-.317,.770),(.040,-.317,.770),.005,12)])
    bmesh.ops.remove_doubles(core,verts=core.verts[:],dist=1e-6)
    bmesh.ops.dissolve_degenerate(core,dist=1e-7,edges=core.edges[:])
    emit(k,core,FRM,'sealed vessel with fused service spine and clamp clevis')
    for z in (.193,.725):
        with k.frame(radial(math.pi/2,.273*math.cos(HALF_FACET),z)):
            socket(k,.007,0,.003,'rear shell seam retainer')

def armour(k):
    # Two broad half-shells with turned-in ends and formed strengthening beads.
    stations=[(.120,.258,.250),(.172,.275,.250),(.205,.275,.250),
              (.214,.271,.250),(.447,.271,.250),(.457,.275,.250),
              (.485,.275,.250),(.495,.271,.250),(.725,.271,.250),
              (.735,.275,.250),(.770,.275,.250),(.820,.258,.250)]
    for first,last in ((3,31),(33,61)):
        shell=sector(stations,first,last)
        shell=common.trim_seats(shell,[k.parts[1]])
        if first==3:
            a=-math.pi/2+5*math.pi/16
            m=radial(a,.271*math.cos(HALF_FACET),.580)
            shell=subtract_bmesh(shell,transformed(rod((0,0,-.005),(0,0,.035),.021,12),m))
        screw_frames=[]
        for j in (first+1,last-1):
            a=-math.pi/2+j*HALF_FACET
            for z in (.190,.750):
                m=radial(a,.275*math.cos(HALF_FACET),z);screw_frames.append(m)
                shell=subtract_bmesh(shell,transformed(rod((0,0,-.003),(0,0,.02),.007,8),m))
        emit(k,shell,PRI,'stamped broad armour cassette')
        for m in screw_frames:
            # A 0.2 mm radial machining clearance avoids the head scraping its
            # pocket wall; the cap is flush, retained by the hidden fastener.
            with k.frame(m):socket(k,.0068,-.00295,0,'armour captive socket screw')
    # A single capped charge connection, wholly within a 53 mm planar facet.
    a=-math.pi/2+5*math.pi/16
    with k.frame(radial(a,.271*math.cos(HALF_FACET),.580)):
        flange=kit.machine(rod((0,0,-.005),(0,0,.012),.021,12),
                           cuts=[((0,0,.006),(0,0,.05),.013,12)])
        emit(k,flange,SEC,'charge socket flange seated in armour')
        emit(k,rod((0,0,.006),(0,0,.028),.013,6),JNT,'threaded charge socket neck')
        plug=kit.machine(rod((0,0,.028),(0,0,.040),.019,8),
                         boxes=[((0,0,.040),(.024,.005,.006))])
        emit(k,plug,JNT,'charge port captive blanking cap')

def gauge(k):
    # Physical spindle and needle behind a gasketed lens, never an LCD.
    with k.frame(radial(-math.pi/2,FRONT_DEPTH,.620)):
        bezel=kit.machine(rod((0,0,-.010),(0,0,.013),.046,24),
                           cuts=[((0,0,-.011),(0,0,.04),.037,24)])
        emit(k,bezel,JNT,'pressure gauge recessed stainless bezel')
        emit(k,rod((0,0,-.010),(0,0,-.002),.037,24),PRI,'analogue pressure gauge dial')
        for i in range(9):
            a=math.radians(225-i*270/8)
            tick=transformed(block((.027,-.0007,-.002),(.032,.0007,-.0015)),Matrix.Rotation(a,4,'Z'))
            emit(k,tick,FRM,'pressure gauge graduation')
        needle=kit.prism_bm([(0,-.002,.001),(.027,-.0008,.001),
                             (.027,.0008,.001),(0,.002,.001)],.002,(0,0,1))
        needle=transformed(needle,Matrix.Rotation(math.radians(115),4,'Z'))
        pointer=kit.machine(rod((0,0,-.002),(0,0,.004),.0045,12),union=[needle])
        emit(k,pointer,FRM,'pressure gauge pointer on its central spindle')
        gasket=kit.machine(rod((0,0,.005),(0,0,.008),.037,24),
                           cuts=[((0,0,.004),(0,0,.009),.034,24)])
        emit(k,gasket,FRM,'pressure instrument lens gasket')
        emit(k,rod((0,0,.008),(0,0,.010),.037,24),GLASS,'sealed pressure gauge lens')

def drain(k):
    with k.frame(radial(-math.pi/2,FRONT_DEPTH,.320)):
        body=kit.machine(rod((0,0,-.010),(0,0,.025),.024,12),
                         union=[block((-.012,.020,.014),(.012,.046,.038))],
                         cuts=[((-.030,.037,.029),(.030,.037,.029),.0045,12)])
        emit(k,body,JNT,'drain valve body with bored lever support')
        emit(k,rod((0,0,.025),(0,0,.036),.019,6),SEC,'closed drain threaded cap')
        emit(k,rod((-.022,.037,.029),(.022,.037,.029),.0045,12),JNT,'drain lever transverse pin')
        lever=kit.machine(rod((.014,.037,.029),(.020,.037,.029),.011,12),
                           union=[block((.014,.037,.025),(.020,.080,.033))],
                           cuts=[((.010,.037,.029),(.024,.037,.029),.0045,12)])
        emit(k,lever,SEC,'closed drain operating lever')
        guard=block((-.047,-.039,0),(-.039,.085,.044))
        guard=kit.machine(guard,union=[block((.039,-.039,0),(.047,.085,.044)),
                                      block((-.045,-.045,.036),(.045,-.037,.044))])
        emit(k,guard,FRM,'drain impact guard with both feet on service spine')

def crown(k):
    top=drum([(.820,.258),(.840,.285),(.855,.300),(.892,.300),
              (.913,.283),(.925,.275)])
    top=kit.machine(top,cuts=[((0,0,.865),(0,0,1.1),.248,32)])
    for a in (0,math.pi):
        top=subtract_bmesh(top,transformed(loft([(.115,.029,.007,-.070),
                                                 (.115,.029,.007,.070)]),radial(a,.280,.899)))
    catch=block((-.024,-.306,.828),(.024,-.265,.856))
    top=kit.machine(top,union=[catch],boxes=[((0,-.301,.843),(.025,.020,.009))])
    emit(k,top,SEC,'lid carrying chime and fused toggle catch')
    gasket=kit.machine(rod((0,0,.865),(0,0,.868),.248,32),
                       cuts=[((0,0,.864),(0,0,.87),.231,32)])
    emit(k,gasket,FRM,'lid perimeter gasket')
    lid=rod((0,0,.868),(0,0,.887),.248,32)
    lid=kit.machine(lid,union=[rod((-.085,-.055,.884),(-.085,-.055,.904),.032,16)],
                    cuts=[((-.085,-.055,.897),(-.085,-.055,.93),.024,12)])
    emit(k,lid,PRI,'closed top cover with fused filling neck')
    plug=kit.machine(rod((-.085,-.055,.897),(-.085,-.055,.910),.024,12),
                     boxes=[((-.085,-.055,.910),(.030,.006,.008))])
    emit(k,plug,JNT,'recessed top filling plug')
    bridge=moved(loft([(.186,.036,.009,.917),(.186,.036,.009,.943),
                       (.176,.026,.006,HEIGHT)]),(0,.094,0))
    grip=kit.machine(block((-.093,.076,.887),(-.073,.112,.923)),
                      union=[block((.073,.076,.887),(.093,.112,.923)),bridge])
    emit(k,grip,SEC,'two-foot top lifting grip')
    for x in (-.16,.16):
        with k.frame(common.frame((x,-.110,.887),(0,0,1),(0,1,0))):
            socket(k,.007,0,.003,'top cover screw')

def latch(k):
    emit(k,rod((-.029,-.317,.770),(.029,-.317,.770),.005,12),JNT,'lid toggle hinge pin')
    m=common.frame((0,-.324,.804),(0,-1,0),(0,0,1))
    lever=transformed(loft([(.030,.086,.006,0),(.030,.086,.006,.009)]),m)
    lever=kit.machine(lever,
        union=[rod((-.016,-.317,.770),(.016,-.317,.770),.010,12),
               block((-.012,-.329,.839),(.012,-.292,.846))],
        cuts=[((-.023,-.317,.770),(.023,-.317,.770),.005,12)])
    emit(k,lever,JNT,'closed lid toggle lever and retained hook')
    rear=kit.machine(block((-.020,.246,.781),(.020,.280,.858)),
                      cuts=[((-.045,.269,.817),(.045,.269,.817),.005,12)])
    rear=common.trim_seats(rear,[p for p,t in zip(k.parts,common.LABELS)
                                 if t in ('sealed vessel with fused service spine and clamp clevis',
                                          'lid carrying chime and fused toggle catch')])
    emit(k,rear,SEC,'rear lid retaining cleat')
    emit(k,rod((-.020,.269,.817),(.020,.269,.817),.005,12),JNT,'rear lid retaining pin')

def main():
    kit.NAME,kit.TITLE=NAME,TITLE
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.MATERIALS={n:kit.MATERIALS[n] for n in (PRI,SEC,FRM,JNT)}
    kit.MATERIALS[GLASS]=((.85,.91,.93),0,.16,0);kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    glass=bpy.data.materials[GLASS];glass.diffuse_color=(.85,.91,.93,.16)
    glass.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value=.16
    glass.surface_render_method='DITHERED'
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[]);k=kit.Kit()
    for fn in (structure,armour,gauge,drain,crown,latch):fn(k)
    pairs=common.exact_intersections(k);kit.check_connectivity(k,joints,[])
    collision_source=[{'label':tag,'vertices':[list(v) for v in p.verts],'triangles':p.faces}
                      for p,tag in zip(k.parts,common.LABELS)]
    body=k.to_object('SK_'+TITLE);kit.skin(body,rig)
    if '--draft' not in sys.argv:
        # Transparent glass must never occlude the analogue dial during the
        # visibility audit. Isolate it temporarily, then restore its geometry.
        lens=bmesh.new();lens.from_mesh(body.data)
        glass_index=kit.SLOTS.index(GLASS)
        bmesh.ops.delete(lens,geom=[f for f in lens.faces if f.material_index!=glass_index],context='FACES_ONLY')
        bmesh.ops.delete(lens,geom=[v for v in lens.verts if not v.link_faces],context='VERTS')
        solid=bmesh.new();solid.from_mesh(body.data)
        bmesh.ops.delete(solid,geom=[f for f in solid.faces if f.material_index==glass_index],context='FACES_ONLY')
        bmesh.ops.delete(solid,geom=[v for v in solid.verts if not v.link_faces],context='VERTS')
        solid.to_mesh(body.data);solid.free()
        kit.cull_unseen(body,rig,joints,[],[('fixed',{})],(-.31,-.36),(.35,.31))
        solid=bmesh.new();solid.from_mesh(body.data);weights=solid.verts.layers.deform.verify()
        vmap={v:solid.verts.new(v.co) for v in lens.verts}
        for v in vmap.values():v[weights][0]=1.0
        for f in lens.faces:
            nf=solid.faces.new([vmap[v] for v in f.verts]);nf.material_index=glass_index;nf.smooth=f.smooth
        solid.to_mesh(body.data);solid.free();lens.free()
    kit.check_coplanar(body);tris=kit.triangles(body);assert tris<=5000,tris
    lo=[min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in body.data.vertices) for i in range(3)]
    assert abs(lo[2])<1e-6 and abs(hi[2]-HEIGHT)<1e-5
    assert max(hi[i]-lo[i] for i in range(3))<=1.0
    assert not bpy.data.actions
    if '--draft' not in sys.argv:
        common.prepare_export([rig,body],HERE,NAME);kit.select_only([rig,body])
        bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}.fbx'),use_selection=True,
            object_types={'MESH','ARMATURE'},global_scale=1,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
            use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
            primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
            bake_anim=False,path_mode='COPY',embed_textures=True)
        bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}.glb'),export_format='GLB',
            use_selection=True,export_yup=True,export_apply=False,export_skins=True,
            export_def_bones=True,export_animations=False,export_materials='EXPORT')
    rig['preview_poses']=json.dumps({})
    report={'name':NAME,'static':True,'animations':[],'units':'metres',
            'triangles':tris,'triangle_budget':5000,'materials':list(kit.MATERIALS),
            'dimensions_m':{'height':HEIGHT,'nominal_diameter':RADIUS*2},
            'bounds_m':{'lo':lo,'hi':hi},'tensor_height_m':1.753,
            'placement':'floor centre z=0; service/front -Y; up +Z',
            'bones':[{'name':ROOT,'kind':'fixed','parent':None}],
            'joints':[{'bone':ROOT,'type':'fixed','parent':None,'pivot':[0,0,0],'range':None}],
            'mechanics':{'type':'sealed service reservoir',
                         'instrument':'analogue gauge with physical pointer and seated lens',
                         'drain':'capped shutoff valve with pinned lever and U guard',
                         'charge':'capped service coupling on a true armour flat',
                         'lid':'gasketed top with front toggle and rear retention cleat',
                         'lift':'two chime grips and two-foot top handle',
                         'armour':'two broad stamped half-shells with strengthening beads'},
            'checks':{'connected_parts':len(k.parts),'exact_solid_pairs':pairs,
                      'no_solid_intersections':True,'coplanar':True,'budget':True,'no_actions':True}}
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    (HERE/f'{NAME}_collision_source_report.json').write_text(json.dumps(collision_source))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles, {len(k.parts)} connected parts, {lo} .. {hi}',flush=True)

if __name__=='__main__':main()
