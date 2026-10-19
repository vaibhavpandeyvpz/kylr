extends RefCounted
## Benchmark-only occluders from the assembled map's opaque floor geometry.
static func install(arena: ArenaMap, viewport: Viewport) -> Dictionary:
	var report := {"meshes":0,"triangles":0,"skinned_bakes":0}
	var roots: Array[Node3D] = []
	for fixture in arena.fixtures:
		if fixture.kind == "platform": roots.append(fixture.node)
	var native_path := "res://assets/models/maps/%s/%s.glb" % [arena.config.model,arena.config.model]
	var sources: Array[MeshInstance3D] = []
	for source: MeshInstance3D in arena.model.find_children("*","MeshInstance3D",true,false):
		if source.mesh == null: continue
		var path: String = source.mesh.get_meta("source_mesh_path",source.mesh.resource_path)
		if path.begins_with(native_path+"::"): sources.append(source)
	for parent in roots:
		for source: MeshInstance3D in parent.find_children("*","MeshInstance3D",true,false):
			if source not in sources: sources.append(source)
	for source in sources:
		if source.mesh == null or not source.is_visible_in_tree(): continue
		var path: String = source.mesh.get_meta("source_mesh_path",source.mesh.resource_path)
		if "/models/maps/" not in path: continue
		var mesh := source.bake_mesh_from_current_skeleton_pose() if source.skin != null else source.mesh
		var vertices := PackedVector3Array()
		var indices := PackedInt32Array()
		for surface in mesh.get_surface_count():
			var material := source.get_active_material(surface) as StandardMaterial3D
			if material == null or material.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED or Assets.material_role(material.resource_name) == "M_Regolith": continue
			if mesh.surface_get_primitive_type(surface) != Mesh.PRIMITIVE_TRIANGLES: continue
			var arrays := mesh.surface_get_arrays(surface)
			var points: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var faces: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			var offset := vertices.size()
			vertices.append_array(points)
			if faces.is_empty():
				for index in points.size(): indices.append(offset+index)
			else:
				for index in faces: indices.append(offset+index)
		if indices.is_empty(): continue
		var shape := ArrayOccluder3D.new()
		shape.set_arrays(vertices,indices)
		var occluder := OccluderInstance3D.new()
		occluder.occluder = shape
		source.add_child(occluder)
		report.meshes += 1
		report.triangles += indices.size()/3
		if source.skin != null: report.skinned_bakes += 1
	viewport.use_occlusion_culling = true
	return report
