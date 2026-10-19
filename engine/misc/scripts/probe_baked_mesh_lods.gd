extends SceneTree
## Run with a graphical renderer: skin palettes must have reached the server.

var failures: Array[String] = []

func _initialize() -> void:
	verify.call_deferred()

func check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)

func verify() -> void:
	var skeleton := Skeleton3D.new()
	root.add_child(skeleton)
	skeleton.add_bone("Root")
	skeleton.set_bone_rest(0, Transform3D.IDENTITY)
	skeleton.set_bone_pose_position(0, Vector3(0.25, 0.5, -0.25))
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([Vector3.ZERO, Vector3.RIGHT, Vector3(1, 1, 0), Vector3.UP])
	arrays[Mesh.ARRAY_NORMAL] = PackedVector3Array([Vector3.BACK, Vector3.BACK, Vector3.BACK, Vector3.BACK])
	arrays[Mesh.ARRAY_INDEX] = PackedInt32Array([0, 1, 2, 0, 2, 3])
	arrays[Mesh.ARRAY_BONES] = PackedInt32Array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
	arrays[Mesh.ARRAY_WEIGHTS] = PackedFloat32Array([1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0])
	var source := ArrayMesh.new()
	source.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays, [], {1.0: PackedInt32Array([0, 1, 2]), 2.0: PackedInt32Array([0, 2, 3])})
	var mesh := MeshInstance3D.new()
	mesh.mesh = source
	var skin := Skin.new()
	skin.add_bind(0, Transform3D.IDENTITY)
	mesh.skin = skin
	skeleton.add_child(mesh)
	mesh.skeleton = mesh.get_path_to(skeleton)
	skeleton.force_update_all_bone_transforms()
	await process_frame
	await RenderingServer.frame_post_draw
	var baked := mesh.bake_mesh_from_current_skeleton_pose()
	check(baked != null and baked.get_surface_count() == 1, "One baked surface expected")
	if baked != null and baked.get_surface_count() == 1:
		var output := baked.surface_get_arrays(0)
		check(output[Mesh.ARRAY_INDEX] == arrays[Mesh.ARRAY_INDEX], "Base indices changed")
		check(output[Mesh.ARRAY_BONES] == null and output[Mesh.ARRAY_WEIGHTS] == null, "Skin attributes remain")
		for vertex in 4:
			check(output[Mesh.ARRAY_VERTEX][vertex].is_equal_approx(arrays[Mesh.ARRAY_VERTEX][vertex] + Vector3(0.25, 0.5, -0.25)), "Baked vertex differs")
		# Serialized surface data retains each LOD's threshold and exact index bytes.
		check(baked.get("_surfaces")[0].get("lods", []) == source.get("_surfaces")[0].get("lods", []), "Imported LODs lost or changed")
		var reused := mesh.bake_mesh_from_current_skeleton_pose(baked)
		check(reused == baked and reused.get_surface_count() == 1, "Existing-mesh reuse changed")
		check(reused.get("_surfaces")[0].get("lods", []) == source.get("_surfaces")[0].get("lods", []), "Reused mesh LODs differ")
	skeleton.free()
	print("BAKED_MESH_LODS ", JSON.stringify({"passed": failures.is_empty(), "failures": failures}))
	quit(0 if failures.is_empty() else 1)
