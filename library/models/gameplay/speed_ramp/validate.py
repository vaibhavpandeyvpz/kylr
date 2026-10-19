"""Fresh GLB/FBX round trips, authored motion and collider topology checks."""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent
INFO=json.loads((HERE/"speed_ramp_rig.json").read_text())
spec=importlib.util.spec_from_file_location("ramp_source",HERE/"model.py")
source=importlib.util.module_from_spec(spec);sys.modules[spec.name]=source;spec.loader.exec_module(source)


def convex_islands(obj):
    bm=bmesh.new();bm.from_mesh(obj.data);bm.normal_update()
    assert all(len(e.link_faces)==2 for e in bm.edges),(obj.name,"open collider")
    remaining=set(bm.verts);count=0
    while remaining:
        seed=remaining.pop();island={seed};pending=[seed]
        while pending:
            for e in pending.pop().link_edges:
                for v in e.verts:
                    if v in remaining:remaining.remove(v);island.add(v);pending.append(v)
        faces={f for v in island for f in v.link_faces}
        volume=sum(t[0].vert.co.dot(t[1].vert.co.cross(t[2].vert.co))/6 for t in bm.calc_loop_triangles() if t[0].face in faces)
        assert volume>1e-8,(obj.name,"inward island",volume)
        for f in faces:
            assert all(f.normal.dot(v.co-f.verts[0].co)<1e-5 for v in island),(obj.name,"non-convex")
        count+=1
    bm.free();return count


def reset(rig):
    rig.animation_data_create();rig.animation_data.action=None
    for track in rig.animation_data.nla_tracks:track.mute=True
    for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()


def use_action(rig,action):
    rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]


def check_geometry():
    bpy.ops.wm.open_mainfile(filepath=str(HERE/"speed_ramp.blend"))
    body=bpy.data.objects["SK_SpeedRamp"];rig=bpy.data.objects["RIG_SpeedRamp"]
    reset(rig)
    deps=bpy.context.evaluated_depsgraph_get()
    groups=[g.name for g in body.vertex_groups]
    body.data.calc_loop_triangles();fixed=[];treads=[]
    for tri in body.data.loop_triangles:
        names={groups[g.group] for vi in tri.vertices for g in body.data.vertices[vi].groups}
        if all("Tread" in n for n in names):treads.append(tuple(tri.vertices))
        elif names=={"Root"}:fixed.append(tuple(tri.vertices))
    frame_bvh=BVHTree.FromPolygons([v.co.copy() for v in body.data.vertices],fixed,all_triangles=True)
    def clearance(label):
        obj=body.evaluated_get(deps);mesh=obj.to_mesh()
        verts=[v.co.copy() for v in mesh.vertices]
        b=BVHTree.FromPolygons(verts,treads,all_triangles=True)
        hits=frame_bvh.overlap(b)
        assert not hits,("Belt intersects stationary frame",label,len(hits),
                         [tuple(verts[v]) for v in fixed[hits[0][0]]])
        assert all(abs(v.x)<=.75001 and abs(v.y)<=.50001 and v.z>=-.00001 for v in verts)
        obj.to_mesh_clear()
    for phase in range(65):
        source.pose_distance(rig,source.PERIMETER*phase/64)
        clearance(f"phase {phase}")
    for degrees in (0,17.5,35):
        source.pose_distance(rig,0,degrees)
        mesh=bpy.data.meshes.new_from_object(body.evaluated_get(deps))
        obj=bpy.data.objects.new("CHECK_Seams",mesh);bpy.context.scene.collection.objects.link(obj)
        source.f.check_coplanar(obj)
        bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
    # Check the actual baked keys and halfway interpolation, not only ideal CAD poses.
    for name in ("convey","launch"):
        action=bpy.data.actions[name];use_action(rig,action)
        for half_frame in range(int(action.frame_range[1])*2+1):
            bpy.context.scene.frame_set(half_frame//2,subframe=(half_frame%2)/2)
            bpy.context.view_layer.update();clearance(f"{name} frame {half_frame/2}")
        print(f"[speed_ramp] {name}: all keys and half-frame interpolation clear",flush=True)
    reset(rig)
    sys.path.insert(0,str(HERE))
    import collision as collider
    pieces=collider.extras.fixed(rig)+collider.extras.cover("Left")(rig)+collider.extras.cover("Right")(rig)
    tris,_=collider.mesh_islands([body],{},rig.matrix_world.inverted())
    worst,share=collider.coverage(pieces,tris)
    assert worst<=.020,("Collider misses rendered surface",worst)
    print(f"[speed_ramp] collider coverage: worst {worst*1000:.2f} mm, {share*100:.1f}% inside")
    print("[speed_ramp] 65 phases: belts clear of frame; evaluated rest/half/open seams PASS")


def check(stem,extension):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=HERE/f"{stem}.{extension}"
    if extension=="glb":bpy.ops.import_scene.gltf(filepath=str(path))
    else:bpy.ops.import_scene.fbx(filepath=str(path))
    meshes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.name.startswith("SK_")]
    rig=next(o for o in bpy.context.scene.objects if o.type=="ARMATURE")
    expected={"Root","Drive","Idler","LeftService","RightService"}|{f"{side}Tread{i:02}" for side in ("Left","Right") for i in range(source.STATIONS)}
    assert set(rig.data.bones.keys())==expected,(extension,rig.data.bones.keys())
    actions={name:next((a for a in bpy.data.actions if name in a.name),None) for name in INFO["animations"]}
    assert all(a and source.f.action_fcurves(a) for a in actions.values())
    reset(rig)
    for o in meshes:
        assert all(abs(s-1)<1e-5 for s in o.scale)
        for v in o.data.vertices:
            weights=[g.weight for g in v.groups if g.weight>1e-6]
            assert len(weights)==1 and abs(weights[0]-1)<1e-5,(o.name,v.index,weights)
    counts={o.name:sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes}
    if stem=="speed_ramp":
        assert counts=={"SK_SpeedRamp":INFO["triangles"]},counts
        o=meshes[0];assert set(m.name for m in o.data.materials)==set(INFO["materials"])
        assert o.data.uv_layers and all(math.isfinite(c) and -1e-5<=c<=1+1e-5 for uv in o.data.uv_layers for t in uv.data for c in t.uv)
        points=[o.matrix_world@v.co for v in o.data.vertices]
        bounds=[[min(v[i] for v in points),max(v[i] for v in points)] for i in range(3)]
        for i,extent in ((0,.75),(1,.5)):
            assert abs(bounds[i][0]+extent)<1e-4 and abs(bounds[i][1]-extent)<1e-4,bounds
        assert abs(bounds[2][0])<1e-4 and abs(bounds[2][1]-.75)<1e-4,bounds
        assert abs(bounds[2][1]-bounds[2][0]-.75)<1e-4,bounds
        marker=bpy.data.objects["LaunchOrigin"]
        assert (marker.matrix_world.translation-Vector(INFO["launch_design"]["launch_origin"])).length<1e-4
    else:
        for mesh in meshes:
            assert all((mesh.matrix_world @ v.co).z >= -1e-5 for v in mesh.data.vertices), (mesh.name,"underground collider")
        assert set(counts)=={"SK_SpeedRampCol","SK_SpeedRampTrigger"},counts
        assert counts["SK_SpeedRampCol"]<=500 and counts["SK_SpeedRampTrigger"]==12
        assert convex_islands(next(o for o in meshes if o.name=="SK_SpeedRampTrigger"))==1
        convex_islands(next(o for o in meshes if o.name=="SK_SpeedRampCol"))
    # Read the imported loop at start, a moving midpoint, and its closing frame.
    use_action(rig,actions["convey"])
    def matrices(frame):
        whole=math.floor(frame)
        bpy.context.scene.frame_set(whole,subframe=frame-whole);bpy.context.view_layer.update()
        return {n:rig.pose.bones[n].matrix.copy() for n in expected}
    first=float(actions["convey"].frame_range[0]);end=float(actions["convey"].frame_range[1])
    a=matrices(first);b=matrices((first+end)/2);c=matrices(end)
    assert (b["LeftTread00"].translation-a["LeftTread00"].translation).length>.20
    worst=max(abs(a[n][r][j]-c[n][r][j]) for n in expected for r in range(4) for j in range(4))
    assert worst<2e-4,(extension,"loop seam",worst)
    use_action(rig,actions["service_open"])
    a=matrices(float(actions["service_open"].frame_range[0]));b=matrices(float(actions["service_open"].frame_range[1]))
    rot=(a["LeftService"].to_3x3().inverted()@b["LeftService"].to_3x3()).to_quaternion().angle
    assert abs(math.degrees(rot)-35)<.02,(extension,"cover hinge angle",rot)
    print(f"[speed_ramp] {path.name}: PASS, {counts}, {len(expected)} bones, 4 clips, loop closure {worst:.2g}")
    return {"file":path.name,"triangles":counts,"status":"PASS","loop_error":worst}


if "--exports-only" not in sys.argv:check_geometry()
if "--geometry-only" not in sys.argv:
    report=[check(s,e) for s in ("speed_ramp","speed_ramp_col") for e in ("glb","fbx")]
    (HERE/"speed_ramp_validation.json").write_text(json.dumps(report,indent=2))
