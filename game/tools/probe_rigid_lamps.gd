extends SceneTree
## Rendered startup regression for every authored static prop, plus late attachments.
func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	var world := Node3D.new()
	root.add_child(world)
	var cases: Array = []
	for category in DirAccess.get_directories_at("res://assets/models"):
		for asset in DirAccess.get_directories_at("res://assets/models/"+category):
			var path := "res://assets/models/%s/%s/%s_rig.json" % [category,asset,asset]
			if not FileAccess.file_exists(path): continue
			var metadata: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
			if not metadata.get("static",false): continue
			var candidate := Assets.model(category,asset)
			var reference := Assets.model(category,asset)
			world.add_child(candidate)
			world.add_child(reference)
			ArchitectureLights.share_static_meshes(candidate)
			cases.append({"asset":asset,"candidate":candidate,"reference":reference})
	# A later-mounted animated object must not be captured by a parent's request.
	var late_attachment := Assets.model("environments","pillar")
	cases[0].candidate.add_child(late_attachment)
	Assets.play(late_attachment,"open")
	# Unloading a prop before the pending bake must also be harmless.
	var removed := Assets.model("environments","sconce_light")
	world.add_child(removed)
	ArchitectureLights.share_static_meshes(removed)
	removed.free()
	await RenderingServer.frame_post_draw
	await process_frame
	var passed := true
	var mesh_count := 0
	for test in cases:
		var maximum_error := 0.0
		var native_meshes: Array = test.reference.find_children("*","MeshInstance3D",true,false)
		for native: MeshInstance3D in native_meshes:
			var candidate: MeshInstance3D = test.candidate.get_node(test.reference.get_path_to(native))
			var expected := native.bake_mesh_from_current_skeleton_pose() if native.skin != null else native.mesh
			passed = passed and candidate.skin==null and candidate.skeleton.is_empty()
			passed = passed and candidate.mesh.get_surface_count()==expected.get_surface_count()
			for surface in expected.get_surface_count():
				var original: Array = expected.surface_get_arrays(surface)
				var cached: Array = candidate.mesh.surface_get_arrays(surface)
				passed = passed and candidate.get_active_material(surface)==native.get_active_material(surface)
				passed = passed and original[Mesh.ARRAY_VERTEX].size()==cached[Mesh.ARRAY_VERTEX].size()
				for slot in [Mesh.ARRAY_NORMAL,Mesh.ARRAY_TANGENT,Mesh.ARRAY_INDEX,Mesh.ARRAY_TEX_UV]:
					passed = passed and original[slot]==cached[slot]
				for index in original[Mesh.ARRAY_VERTEX].size():
					maximum_error=maxf(maximum_error,original[Mesh.ARRAY_VERTEX][index].distance_to(cached[Mesh.ARRAY_VERTEX][index]))
			mesh_count += 1
		for native: Node3D in test.reference.find_children("*","Node3D",true,false):
			if native is PhysicalBoneSimulator3D: continue # Engine-generated unique node names.
			var candidate: Node3D = test.candidate.get_node(test.reference.get_path_to(native))
			passed = passed and native.global_transform.is_equal_approx(candidate.global_transform)
		passed = passed and maximum_error<0.00001
		print("STATIC_CACHE ",test.asset," max_vertex_error=",maximum_error," passed=",passed)
	for mesh: MeshInstance3D in late_attachment.find_children("*","MeshInstance3D",true,false):
		passed = passed and mesh.skin != null
	print("STATIC_CACHE_SUMMARY assets=",cases.size()," meshes=",mesh_count," late_attachment_animated=true passed=",passed)
	world.queue_free()
	await process_frame
	quit(0 if passed else 1)
