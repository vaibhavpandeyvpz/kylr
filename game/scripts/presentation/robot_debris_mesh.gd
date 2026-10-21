class_name RobotDebrisMesh
extends RefCounted
## Immutable, bone-local render fragments derived from the authored rigid skin.
## Instances retain their own painted materials; the cache never owns appearance.
static var cache: Dictionary = {}

static func fragments(source: MeshInstance3D, skeleton: Skeleton3D) -> Array:
	var key := "%s/%s" % [source.mesh.get_instance_id(), source.skin.get_instance_id()]
	if cache.has(key): return cache[key]
	var result: Array = []
	for surface in source.mesh.get_surface_count():
		var arrays := source.mesh.surface_get_arrays(surface)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
		var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
		var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		if bones.is_empty(): continue
		var stride: int = bones.size() / vertices.size()
		var partitions: Dictionary = {}
		for vertex in vertices.size():
			var bind := bones[vertex * stride]
			assert(is_equal_approx(weights[vertex * stride], 1.0), "Debris requires rigid skin weights")
			if not partitions.has(bind): partitions[bind] = []
			partitions[bind].append(vertex)
		if indices.is_empty():
			for vertex in vertices.size(): indices.append(vertex)
		for bind: int in partitions:
			var bone := String(source.skin.get_bind_name(bind))
			if bone.is_empty(): bone = skeleton.get_bone_name(source.skin.get_bind_bone(bind))
			var inverse_bind := source.skin.get_bind_pose(bind)
			var normal_basis := inverse_bind.basis.inverse().transposed()
			var fragment: Array = []
			fragment.resize(Mesh.ARRAY_MAX)
			var remap: Dictionary = {}
			for vertex: int in partitions[bind]:
				remap[vertex] = remap.size()
			for attribute in [Mesh.ARRAY_VERTEX, Mesh.ARRAY_NORMAL, Mesh.ARRAY_TANGENT, Mesh.ARRAY_COLOR, Mesh.ARRAY_TEX_UV, Mesh.ARRAY_TEX_UV2]:
				if arrays[attribute] == null or arrays[attribute].is_empty(): continue
				var values = arrays[attribute].duplicate()
				values.clear()
				for vertex: int in partitions[bind]:
					if attribute == Mesh.ARRAY_TANGENT:
						var tangent := (inverse_bind.basis * Vector3(arrays[attribute][vertex*4], arrays[attribute][vertex*4+1], arrays[attribute][vertex*4+2])).normalized()
						values.append_array(PackedFloat32Array([tangent.x, tangent.y, tangent.z, arrays[attribute][vertex*4+3]]))
					elif attribute == Mesh.ARRAY_VERTEX: values.append(inverse_bind * vertices[vertex])
					elif attribute == Mesh.ARRAY_NORMAL: values.append((normal_basis * arrays[attribute][vertex]).normalized())
					else: values.append(arrays[attribute][vertex])
				fragment[attribute] = values
			var triangles := PackedInt32Array()
			for triangle in range(0, indices.size(), 3):
				if not remap.has(indices[triangle]): continue
				for corner in 3:
					assert(remap.has(indices[triangle+corner]), "A rigid fragment triangle must belong to one bone")
					triangles.append(remap[indices[triangle+corner]])
			if triangles.is_empty(): continue
			fragment[Mesh.ARRAY_INDEX] = triangles
			var mesh := ArrayMesh.new()
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, fragment)
			result.append({"bone":bone, "mesh":mesh, "surface":surface})
	cache[key] = result
	return result

static func prepare(visual: Node3D) -> void:
	var skeleton := Assets.find(visual, "Skeleton3D") as Skeleton3D
	for source: MeshInstance3D in visual.find_children("*", "MeshInstance3D", true, false):
		if source.skin != null: fragments(source, skeleton)
