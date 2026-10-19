"""Room-preserving convex blockers and independent cargo occupancy area."""
import json
import sys
from pathlib import Path
import bmesh
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import model as source
import collision_extras as extras
HERE=Path(__file__).resolve().parent
NAME=HERE.name

def hull(points,bone='Root'):
    bm=bmesh.new();vs=[bm.verts.new(source.dimensions.point(NAME,p)) for p in points]
    bmesh.ops.convex_hull(bm,input=vs,use_existing_faces=False)
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:]);bmesh.ops.triangulate(bm,faces=bm.faces[:])
    bm.verts.index_update()
    v=[list(p.co) for p in bm.verts];f=[[p.index for p in face.verts] for face in bm.faces];bm.free()
    return dict(bone=bone,V=v,T=f)

def box(lo,hi,bone='Root'):return hull([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],bone)

def mesh(name,pieces,rig):
    verts=[];faces=[];weights={}
    for p in pieces:
        start=len(verts);verts.extend(p['V']);faces.extend([[start+i for i in f] for f in p['T']])
        weights.setdefault(p['bone'],[]).extend(range(start,len(verts)))
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj)
    for bone,indices in weights.items():obj.vertex_groups.new(name=bone).add(indices,1,'REPLACE')
    source.kit.skin(obj,rig)
    return obj

def main():
    bpy.ops.wm.open_mainfile(filepath=str(HERE/f'{NAME}.blend'))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    extras.hull,extras.box=hull,box
    pieces=extras.blockers()
    count=sum(len(p['T']) for p in pieces)
    groups=[[],[]];size=0
    for p in pieces:
        group=0 if size+len(p['T'])<=480 else 1
        groups[group].append(p)
        if group==0:size+=len(p['T'])
    solids=[mesh(name,ps,rig) for name,ps in zip(('SK_BastionStructureCol','SK_BastionEntryLiftCol'),groups)]
    assert all(source.kit.triangles(o)<=500 for o in solids)
    trigger=mesh('SK_BastionLiftPlatformTrigger',extras.trigger(),rig)
    trigger['collision_role']='occupancy_area';trigger['solid_blocker']=False
    trigger['bone']='CargoLift'
    for obj in solids:obj['collision_role']='solid_blockers'
    source.kit.select_only([rig,*solids,trigger])
    from door_actions import install_fbx_filter
    install_fbx_filter()
    bpy.ops.export_scene.fbx(filepath=str(HERE/f'{NAME}_col.fbx'),use_selection=True,
        object_types={'MESH','ARMATURE'},global_scale=1,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',
        use_mesh_modifiers=False,mesh_smooth_type='OFF',add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,
        bake_anim=True,bake_anim_simplify_factor=0,bake_anim_use_all_bones=False,
        bake_anim_use_nla_strips=False,bake_anim_use_all_actions=True,bake_anim_force_startend_keying=False)
    bpy.ops.export_scene.gltf(filepath=str(HERE/f'{NAME}_col.glb'),export_format='GLB',
        use_selection=True,export_yup=True,export_apply=False,export_skins=True,
        export_def_bones=True,export_animations=True,export_animation_mode='ACTIONS',
        export_anim_single_armature=True,export_reset_pose_bones=True,export_force_sampling=True,export_extras=True)
    from door_actions import isolate_glb
    isolate_glb(HERE/f'{NAME}_col.glb')
    for o in bpy.context.scene.objects:
        if o.type=='MESH' and o not in (*solids,trigger):o.hide_render=True
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE/f'{NAME}_col.blend'))
    (HERE/f'{NAME}_collision_report.json').write_text(json.dumps(dict(blocker_triangles=count,
        convex_pieces=len(pieces),trigger_triangles=12,trigger='SK_BastionLiftPlatformTrigger',
        trigger_bone='CargoLift',trigger_role='occupancy area, not blocker',passed=True),indent=2))
    print(f'[{NAME}] collision PASS: {count} blocker triangles; independent platform trigger',flush=True)

if __name__=='__main__':main()
