class_name CollisionRig
extends RefCounted
static var hull_cache: Dictionary = {}

static func moving_carrier(node: Node) -> bool:
	while node!=null:
		if node.get_meta("moving_platform",false):return true
		node=node.get_parent()
	return false

static func world_body(parent: Node) -> StaticBody3D:
	var body: StaticBody3D=AnimatableBody3D.new() if moving_carrier(parent) else StaticBody3D.new()
	if body is AnimatableBody3D:body.sync_to_physics=false
	return body

static func install(visual: Node3D, category: String, id: String, owner_robot = null, suffix := "_col") -> void:
	var source := Assets.model(category, id, suffix)
	var target_skeleton := Assets.find(visual, "Skeleton3D") as Skeleton3D
	var source_skeleton := Assets.find(source, "Skeleton3D") as Skeleton3D
	for mesh_node in source.find_children("*", "MeshInstance3D", true, false):
		if owner_robot != null and String(mesh_node.name).begins_with("SK_TensorUpperBody") and not String(mesh_node.name).trim_suffix("Col").to_lower().ends_with(owner_robot.upper_body): continue
		if owner_robot != null and String(mesh_node.name).begins_with("SK_TensorHead") and not String(mesh_node.name).to_lower().contains(owner_robot.head): continue
		if String(mesh_node.name).contains("Trigger") or String(mesh_node.name).contains("Shield"): continue
		var hit_region := "head" if owner_robot != null and String(mesh_node.name).begins_with("SK_TensorHead") else "body"
		if mesh_node.skin != null and target_skeleton != null and source_skeleton != null:
			var cache_key := category + "/" + id + suffix + "/" + String(mesh_node.name)
			cache_key += "/convex" if owner_robot != null else "/surface"
			if not hull_cache.has(cache_key):
				hull_cache[cache_key] = split_hulls(mesh_node,source_skeleton) if owner_robot != null else bone_surfaces(mesh_node,source_skeleton)
			var bodies: Dictionary = {}
			for hull in hull_cache[cache_key]:
				if target_skeleton.find_bone(hull.bone)<0: continue
				if bodies.has(hull.bone):
					add_shape(null,hull.shape,owner_robot,hit_region,String(mesh_node.name),bodies[hull.bone])
					continue
				var attachment:=BoneAttachment3D.new()
				attachment.bone_name=hull.bone
				target_skeleton.add_child(attachment)
				bodies[hull.bone] = add_shape(attachment,hull.shape,owner_robot,hit_region,String(mesh_node.name))
			continue
		else:
			var body := world_body(visual)
			body.collision_layer = 1
			body.collision_mask = 0
			body.set_meta("spatio_material", Spatio.material_for_name(String(mesh_node.name), category))
			body.set_meta("lethal_surface", String(mesh_node.name).contains("LethalSurface"))
			visual.add_child(body)
			var transform := Transform3D.IDENTITY
			var cursor: Node = mesh_node
			while cursor != source:
				if cursor is Node3D: transform = cursor.transform * transform
				cursor = cursor.get_parent()
			body.transform = transform
			var shape_node := CollisionShape3D.new()
			shape_node.shape = mesh_node.mesh.create_trimesh_shape()
			body.add_child(shape_node)
	source.free()

static func install_pickup_area(visual: Node3D, category: String, id: String, suffix := "_ammo_col") -> Area3D:
	var source := Assets.model(category, id, suffix)
	var area := Area3D.new()
	area.collision_layer = 0
	area.collision_mask = 2
	visual.add_child(area)
	for mesh_node in source.find_children("*", "MeshInstance3D", true, false):
		var collision := CollisionShape3D.new()
		collision.shape = mesh_node.mesh.create_convex_shape()
		var transform := Transform3D.IDENTITY
		var cursor: Node = mesh_node
		while cursor != source:
			if cursor is Node3D: transform = cursor.transform * transform
			cursor = cursor.get_parent()
		collision.transform = transform
		area.add_child(collision)
	source.free()
	assert(area.get_child_count() > 0, "Ammo pickup needs an authored collision mesh")
	return area

static func install_trigger(visual: Node3D, category: String, id: String, mesh_name: String, suffix := "_col") -> Area3D:
	var source := Assets.model(category, id, suffix)
	var target_skeleton := Assets.find(visual, "Skeleton3D") as Skeleton3D
	var source_skeleton := Assets.find(source, "Skeleton3D") as Skeleton3D
	var trigger_mesh: MeshInstance3D
	for candidate in source.find_children("*", "MeshInstance3D", true, false):
		if String(candidate.name) == mesh_name:
			trigger_mesh = candidate
			break
	assert(trigger_mesh != null, "Missing authored trigger: " + id + "/" + mesh_name)
	if trigger_mesh != null and trigger_mesh.skin == null:
		var area := Area3D.new()
		area.name = mesh_name
		area.collision_layer = 0
		area.collision_mask = 2
		visual.add_child(area)
		var transform := Transform3D.IDENTITY
		var cursor: Node = trigger_mesh
		while cursor != source:
			if cursor is Node3D: transform = cursor.transform * transform
			cursor = cursor.get_parent()
		area.transform = transform
		var shape := trigger_mesh.mesh.create_convex_shape()
		shape.margin = 0.001
		var collision := CollisionShape3D.new()
		collision.shape = shape
		area.add_child(collision)
		source.free()
		return area
	assert(trigger_mesh != null and trigger_mesh.skin != null and target_skeleton != null and source_skeleton != null,
		"Missing authored trigger or skeleton: " + id + "/" + mesh_name)
	if trigger_mesh == null or trigger_mesh.skin == null or target_skeleton == null or source_skeleton == null:
		source.free()
		return null
	var points := PackedVector3Array()
	var bone_name := ""
	for surface in trigger_mesh.mesh.get_surface_count():
		var arrays := trigger_mesh.mesh.surface_get_arrays(surface)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var bones = arrays[Mesh.ARRAY_BONES]
		var weights = arrays[Mesh.ARRAY_WEIGHTS]
		var stride: int = bones.size() / vertices.size()
		for vertex in vertices.size():
			var best := 0
			for influence in stride:
				if weights[vertex * stride + influence] > weights[vertex * stride + best]: best = influence
			var bind: int = bones[vertex * stride + best]
			var name := String(trigger_mesh.skin.get_bind_name(bind))
			if name.is_empty(): name = String(source_skeleton.get_bone_name(trigger_mesh.skin.get_bind_bone(bind)))
			if bone_name.is_empty(): bone_name = name
			assert(name == bone_name, "A trigger mesh must follow one authored bone: " + mesh_name)
			points.append(trigger_mesh.skin.get_bind_pose(bind) * vertices[vertex])
	assert(points.size() >= 4 and target_skeleton.find_bone(bone_name) >= 0,
		"Invalid authored trigger: " + id + "/" + mesh_name)
	var attachment := BoneAttachment3D.new()
	attachment.name = mesh_name + "Attachment"
	attachment.bone_name = bone_name
	target_skeleton.add_child(attachment)
	var area := Area3D.new()
	area.name = mesh_name
	area.collision_layer = 0
	area.collision_mask = 2
	attachment.add_child(area)
	var shape := ConvexPolygonShape3D.new()
	shape.points = points
	shape.margin = 0.001
	var collision := CollisionShape3D.new()
	collision.shape = shape
	area.add_child(collision)
	source.free()
	return area

static func add_shape(parent: Node3D, shape: Shape3D, robot, hit_region := "body", hit_mesh := "", existing: StaticBody3D = null) -> StaticBody3D:
	var body := existing
	if body == null:
		body = AnimatableBody3D.new() if (parent is BoneAttachment3D and parent.bone_name=="CargoLift") or moving_carrier(parent) else StaticBody3D.new()
		if body is AnimatableBody3D:body.sync_to_physics=false
		body.collision_layer = 4 if robot != null else 1
		body.collision_mask = 0
		if robot == null:
			if not hit_mesh.is_empty(): body.name=hit_mesh
			body.set_meta("spatio_material", "metal")
			body.set_meta("lethal_surface", hit_mesh.contains("LethalSurface"))
		if robot != null:
			body.set_meta("robot", robot)
			body.set_meta("hit_region", hit_region)
			body.set_meta("hit_mesh", hit_mesh)
		parent.add_child(body)
		if robot != null: robot.hit_rids.append(body.get_rid())
	var node := CollisionShape3D.new()
	node.shape = shape
	body.add_child(node)
	return body

static func bone_surfaces(mesh_node: MeshInstance3D, skeleton: Skeleton3D) -> Array:
	# Preserve holes in authored collision shells, including the arena pit.
	var faces: Dictionary = {}
	for surface in mesh_node.mesh.get_surface_count():
		var arrays := mesh_node.mesh.surface_get_arrays(surface)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var bones = arrays[Mesh.ARRAY_BONES]
		var weights = arrays[Mesh.ARRAY_WEIGHTS]
		var indices = arrays[Mesh.ARRAY_INDEX]
		if bones == null or bones.is_empty(): continue
		var stride: int = bones.size() / vertices.size()
		if indices == null or indices.is_empty(): indices = range(vertices.size())
		for triangle in range(0,indices.size(),3):
			for corner in 3:
				var vertex: int = indices[triangle+corner]
				var best := 0
				for influence in stride:
					if weights[vertex*stride+influence]>weights[vertex*stride+best]: best=influence
				var bind: int = bones[vertex*stride+best]
				var bone := mesh_node.skin.get_bind_name(bind)
				if bone == &"": bone = skeleton.get_bone_name(mesh_node.skin.get_bind_bone(bind))
				if not faces.has(bone): faces[bone] = PackedVector3Array()
				faces[bone].append(mesh_node.skin.get_bind_pose(bind)*vertices[vertex])
	var result: Array = []
	for bone in faces:
		var shape := ConcavePolygonShape3D.new()
		shape.set_faces(faces[bone])
		result.append({"bone":bone,"shape":shape})
	return result

static func split_hulls(mesh_node: MeshInstance3D,source_skeleton: Skeleton3D) -> Array:
	var vertices_by_key: Dictionary={}
	var positions: Array[Vector3]=[]
	var bone_names: Array[StringName]=[]
	var neighbors: Array=[]
	for surface in mesh_node.mesh.get_surface_count():
		var arrays:=mesh_node.mesh.surface_get_arrays(surface)
		var vertices: PackedVector3Array=arrays[Mesh.ARRAY_VERTEX]
		var bones=arrays[Mesh.ARRAY_BONES]
		var weights=arrays[Mesh.ARRAY_WEIGHTS]
		var indices=arrays[Mesh.ARRAY_INDEX]
		if bones==null or bones.size()==0: continue
		var stride: int=bones.size()/vertices.size()
		var remap: Array[int]=[]
		for i in vertices.size():
			var best:=0
			for j in stride:
				if weights[i*stride+j]>weights[i*stride+best]: best=j
			var bind: int=bones[i*stride+best]
			var bone: StringName=mesh_node.skin.get_bind_name(bind)
			if bone==&"": bone=source_skeleton.get_bone_name(mesh_node.skin.get_bind_bone(bind))
			var p: Vector3=mesh_node.skin.get_bind_pose(bind)*vertices[i]
			var key:=String(bone)+str(p.snapped(Vector3.ONE*0.00001))
			if not vertices_by_key.has(key):
				vertices_by_key[key]=positions.size()
				positions.append(p)
				bone_names.append(bone)
				neighbors.append([])
			remap.append(vertices_by_key[key])
		if indices==null or indices.size()==0: indices=range(vertices.size())
		for i in range(0,indices.size(),3):
			for j in 3:
				var a: int=remap[indices[i+j]]
				var b: int=remap[indices[i+(j+1)%3]]
				if bone_names[a]==bone_names[b]:
					neighbors[a].append(b)
					neighbors[b].append(a)
	var visited: Dictionary={}
	var result: Array=[]
	for seed in positions.size():
		if visited.has(seed): continue
		var queue: Array=[seed]
		var points:=PackedVector3Array()
		visited[seed]=true
		while not queue.is_empty():
			var current: int=queue.pop_back()
			points.append(positions[current])
			for next in neighbors[current]:
				if not visited.has(next): visited[next]=true; queue.append(next)
		if points.size()>=4:
			var shape:=ConvexPolygonShape3D.new()
			shape.points=points
			result.append({"bone":bone_names[seed],"shape":shape})
	return result
