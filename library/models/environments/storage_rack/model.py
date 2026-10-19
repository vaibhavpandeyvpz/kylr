"""Static industrial storage rack; metres, floor-centred origin, front -Y.

Build with Blender 5.2 headless from library/. No animated mechanisms.
Lofted posts, fused pierced end castings, seated grate cassettes and bins.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Frame': 'Diffuse',
    'M_Joint': 'Metallic',
    'M_Primary': 'Metallic',
    'M_Secondary': 'Metallic',
}
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import light_common as common

kit, ROOT = common.kit, common.ROOT
NAME, TITLE = 'storage_rack', 'StorageRack'
PRI, SEC, FRM, JNT = kit.PRI, kit.SEC, kit.FRM, kit.JNT
emit, block, loft, rod = common.emit, common.block, common.loft, common.rod
SHELVES = (.36, .97, 1.58)
POST_X, POST_Y = .67, .27


def moved(bm, at):
    for v in bm.verts:
        v.co += Vector(at)
    return bm


def casting(k, stations, mat, tag, at=(0, 0, 0), **cuts):
    emit(k, kit.machine(moved(loft(stations), at), **cuts), mat, tag)


def posts(k):
    for x in (-POST_X, POST_X):
        for y in (-POST_Y, POST_Y):
            casting(k, [(.15,.15,.012,0),(.15,.15,.012,.015),
                        (.13,.13,.009,.03),(.10,.10,.007,.046)], JNT,
                    'load-spreading floor shoe', at=(x,y,0),
                    cuts=[((x+dx,y+dy,.018),(x+dx,y+dy,.05),.005,8)
                          for dx,dy in ((-.052,-.052),(.052,.052))])
            # Raised central land receives the post. Bolts sit wholly on its
            # two recessed diagonal corner pads, clear of the shoulder.
            for dx,dy in ((-.052,-.052),(.052,.052)):
                common.bolt(k,x+dx,y+dy,.018,'foot anchor socket',.005)
            body=moved(loft([(.08,.08,.007,.046),(.08,.08,.007,.10),
                             (.08,.08,.007,1.865),(.074,.074,.005,1.90)]),(x,y,0))
            # Blind, 8 mm adjustment sockets; reserved shelf mounting zones
            # remain solid. Recessed armour seats have exact mating planes.
            cuts=[((x,y-.06,z),(x,y-.027,z),.004,8)
                  for z in (.13,.25,.51,1.14,1.70,1.82)]
            pockets=[((x,y-.043,z),(.045,.018,.25)) for z in (.75,1.38)]
            body=kit.machine(body,cuts=cuts,boxes=pockets)
            emit(k,body,FRM,'lofted structural upright')
            for z in (.75,1.38):
                emit(k,block((x-.0215,y-.040,z-.124),
                             (x+.0215,y-.034,z+.124)),PRI,'flush upright wear panel')


def ends(k):
    for x in (-POST_X, POST_X):
        for z0,z1 in ((.36,.91),(.97,1.52),(1.58,1.85)):
            # A single X-web casting: four triangular lightening openings
            # leave joined diagonal ribs and a broad central node. End edges
            # are square butt joints on the uprights' inside flats.
            mid=(z0+z1)/2
            outline=[(x,-.23,z0),(x,.23,z0),(x,.23,z1),(x,-.23,z1)]
            h=(z1-z0)/2
            holes=[[(x,-.172,z0+.036),(x,.172,z0+.036),(x,0,mid-.046)],
                   [(x,-.172,z1-.036),(x,0,mid+.046),(x,.172,z1-.036)],
                   [(x,-.194,z0+.072),(x,-.044,mid),(x,-.194,z1-.072)],
                   [(x,.194,z0+.072),(x,.194,z1-.072),(x,.044,mid)]]
            # Short top bay uses a plain horizontal tie rather than a tiny X.
            if h<.20:
                holes=[[(x,-.194,z0+.045),(x,.194,z0+.045),
                        (x,.194,z1-.045),(x,-.194,z1-.045)]]
            core=kit.machine(kit.prism_bm(outline,.038,(1,0,0)),
                             subtract=[(p,(1,0,0),.10) for p in holes])
            emit(k,core,SEC,'pierced integral end-frame web')


def shelves(k):
    for top in SHELVES:
        # Deck shroud's outer planes contact the posts exactly at x=+/- .63.
        # Four punched seats leave a continuous longitudinal centre spine.
        openings=[(x,y) for x in (-.32,.32) for y in (-.13,.13)]
        shell=loft([(1.26,.54,.013,top-.070),(1.26,.54,.013,top-.056),
                    (1.26,.54,.013,top-.010),(1.24,.52,.008,top)])
        shell=kit.machine(shell,boxes=[((x,y,top),(.52,.19,.18)) for x,y in openings]+
                          [((0,-.273,top-.037),(1.07,.018,.024))])
        emit(k,shell,PRI,'lofted folded shelf shroud')
        emit(k,block((-.534,-.270,top-.049),(.534,-.264,top-.025)),SEC,
             'flush front beam wear strip')
        for x,y in openings:
            # Self-contained punched grate with perimeter and transverse bars.
            # Perimeter uses a 1 mm assembly gap in its seat; underside is
            # carried on the surrounding continuous sill below the aperture.
            grate=block((-.259,-.094,top-.012),(.259,.094,top-.004))
            grate=kit.machine(grate,boxes=[((i*.081,0,top-.008),(.073,.166,.04))
                                          for i in (-2.5,-1.5,-.5,.5,1.5,2.5)])
            emit(k,moved(grate,(x,y,0)),JNT,'punched removable grate cassette')
            # Ledge under the cassette, but entirely outside the punched hole.
            # Shelf bearing lip crosses into the opening by 4 mm, stops exactly
            # at the cassette underside, and is welded onto the shroud wall.
            ledge=kit.machine(block((-.26,-.095,top-.022),(.26,.095,top-.012)),
                              boxes=[((0,0,top-.017),(.49,.16,.04))])
            emit(k,moved(ledge,(x,y,0)),SEC,'grate seating sill')
        for x in (-.60,.60):
            # Connection tabs land on post inner faces; shelf shell itself
            # carries the load. These are visible retained mounting screws.
            with k.frame(common.frame((x,-.27,top-.036),(0,-1,0),(0,0,1))):
                common.bolt(k,0,0,0,'shelf beam retaining screw',.006)


def bin_shell(k, x, y, top):
    # A thick-walled open-front industrial picking bin, flat sole and sloped
    # front mouth. Walls and the bottom are one watertight casting, no hidden
    # overlapping cubes. Front lip 110 mm; rear wall 240 mm.
    z=top
    profile=[(-.19,z),(.19,z),(.19,z+.24),(-.07,z+.24),(-.19,z+.11)]
    rings=[[(x+d,y+yy,zz) for yy,zz in profile] for d in (-.145,.145)]
    shell=kit.loft_rings(rings)
    inner=[(x,y-.177,z+.014),(x,y+.176,z+.014),(x,y+.176,z+.30),
           (x,y-.055,z+.30),(x,y-.177,z+.126)]
    shell=kit.machine(shell,subtract=[(inner,(1,0,0),.262)],
                      boxes=[((x,y-.192,z+.061),(.19,.012,.028))])
    emit(k,shell,SEC,'one-piece sloped picking bin')
    # Label is recessed into the uninterrupted short front wall, flush.
    emit(k,block((x-.094,y-.190,z+.047),(x+.094,y-.186,z+.075)),PRI,
         'flush picking-bin label')


def contents(k):
    for x in (-.43,-.11):bin_shell(k,x,0,SHELVES[2])
    for x in (.11,.43):bin_shell(k,x,0,SHELVES[1])
    # Three concentric turns represent one loosely spiralled power cable.
    # The lower generatrix rests on the centre deck spine; connector ferrules
    # cap both physical ends. This is loose stored cable, not live wiring.
    points=[]
    steps=42
    for i in range(steps+1):
        a=2*math.pi*3*i/steps
        r=.077+.048*i/steps
        points.append(Vector((.34+r*math.cos(a),r*math.sin(a),1.587)))
    rows=[]
    for i,p in enumerate(points):
        tangent=(points[min(i+1,steps)]-points[max(i-1,0)]).normalized()
        u=Vector((0,0,1));v=tangent.cross(u).normalized()
        rows.append([p+.007*(u*math.cos(j*math.tau/6)+v*math.sin(j*math.tau/6)) for j in range(6)])
    emit(k,kit.loft_rings(rows),FRM,'continuous three-turn stored cable')
    for i,j in ((0,1),(steps,steps-1)):
        direction=(points[i]-points[j]).normalized()
        end=rows[i]
        ferrule=kit.loft_rings([end,[p+direction*.008 for p in end]])
        emit(k,ferrule,JNT,'stored cable end ferrule')


def seated(a,b):
    """Also test edge interiors: broad bin soles bridge narrow shelf spines."""
    if a.touches(b,tol=.0001):return True
    if any(a.lo[d]>b.hi[d]+.0001 or b.lo[d]>a.hi[d]+.0001 for d in range(3)):return False
    for p,q in ((a,b),(b,a)):
        for face in p.faces:
            for i,j in zip(face,face[1:]+face[:1]):
                for t in (.25,.5,.75):
                    dist=q.bvh.find_nearest(p.verts[i].lerp(p.verts[j],t))[3]
                    if dist is not None and dist<.0001:return True
    return False


def main():
    kit.NAME,kit.TITLE=NAME,TITLE
    common.CORNER_STEPS=1;common.LABELS.clear()
    kit.MATERIALS={name:kit.MATERIALS[name] for name in (PRI,SEC,FRM,JNT)}
    kit.SLOTS=list(kit.MATERIALS)
    kit.reset_scene();kit.build_materials()
    kit.JOINT_SPECS=[(ROOT,None,'fixed',(0,0,0),(1,0,0),(0,0,1),None)]
    joints=kit.resolve_joints();rig=kit.build_rig(joints,[])
    rig['preview_poses']=json.dumps({})
    k=kit.Kit()
    for fn in (posts,ends,shelves,contents):fn(k)
    pairs=common.exact_intersections(k)
    pending=set(range(1,len(k.parts)));connected={0}
    while pending:
        found={i for i in pending if any(seated(k.parts[i],k.parts[j]) for j in connected)}
        assert found,('disconnected parts',[common.LABELS[i] for i in sorted(pending)])
        connected.update(found);pending-=found
    body=k.to_object('SK_'+TITLE);kit.skin(body,rig)
    # Exact booleans retain collinear cutter splits. Remove these on planar
    # surfaces while preserving every material boundary and hard edge.
    bm=bmesh.new();bm.from_mesh(body.data)
    bmesh.ops.dissolve_limit(bm,angle_limit=.00001,use_dissolve_boundaries=True,
                            verts=bm.verts[:],edges=bm.edges[:],delimit={'MATERIAL'})
    bm.to_mesh(body.data);bm.free()
    if '--draft' not in sys.argv:
        kit.cull_unseen(body,rig,joints,[],[('fixed',{})],(-.745,-.345),(.745,.345))
    kit.check_coplanar(body)
    tris=kit.triangles(body)
    if '--draft' not in sys.argv:assert tris<=5000,tris
    assert not bpy.data.actions
    lo=[min(v.co[i] for v in body.data.vertices) for i in range(3)]
    hi=[max(v.co[i] for v in body.data.vertices) for i in range(3)]
    assert abs(lo[2])<1e-6 and abs(hi[2]-1.90)<1e-5
    objects=[rig,body]
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
            'bounds_m':{'lo':lo,'hi':hi},'tensor_height_m':1.753,'shelf_tops_m':list(SHELVES),
            'placement':'floor centre z=0; access/front -Y; up +Z',
            'materials':list(kit.MATERIALS),'bones':[{'name':ROOT,'kind':'fixed','parent':None}],
            'joints':[{'bone':ROOT,'type':'fixed','parent':None,'pivot':[0,0,0],'range':None}],
            'checks':{'connected_parts':len(k.parts),'exact_solid_pairs':pairs,
                      'no_solid_intersections':True,'coplanar':True,'budget':True,'no_actions':True}}
    (HERE/f'{NAME}_rig.json').write_text(json.dumps(report,indent=2))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    print(f'[{NAME}] PASS: {tris} triangles; {len(k.parts)} connected parts; {lo} .. {hi}',flush=True)


if __name__=='__main__':main()
