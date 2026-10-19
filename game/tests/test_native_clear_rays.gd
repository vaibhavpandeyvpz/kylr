extends GutTest

class RayWorld extends Node3D:
	var robots: Array = []

func test_boolean_visibility_matches_closest_hit_in_clutter_and_after_changes():
	var world := RayWorld.new()
	add_child_autofree(world)
	var random := RandomNumberGenerator.new()
	random.seed = 1606
	var bodies: Array[StaticBody3D] = []
	for index in 24:
		var body := StaticBody3D.new()
		body.collision_layer = 1 if index % 2 == 0 else 8
		var collision := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = Vector3(0.3, 0.5, 0.8)
		collision.shape = shape
		body.add_child(collision)
		world.add_child(body)
		body.position = Vector3(random.randf_range(-3, 3), random.randf_range(-1, 1), random.randf_range(-3, 3))
		body.rotation.y = random.randf_range(-PI, PI)
		bodies.append(body)
	await wait_physics_frames(2)
	var space = world.get_world_3d().direct_space_state
	for changed in [false, true]:
		if changed:
			# Query immediately after mutation: no physics step or cached answer.
			for body in bodies: body.position += Vector3(8, 0, 0)
		for sample_index in 128:
			var from := Vector3(random.randf_range(-4, 12), random.randf_range(-1, 1), random.randf_range(-4, 4))
			var to := Vector3(random.randf_range(-4, 12), random.randf_range(-1, 1), random.randf_range(-4, 4))
			if sample_index < bodies.size(): from = bodies[sample_index].position
			if sample_index % 17 == 0: to = from
			for mask in [0, 1, 8, 9]:
				var query := PhysicsRayQueryParameters3D.create(from, to, mask)
				query.hit_from_inside = sample_index % 2 == 0
				query.hit_back_faces = sample_index % 3 == 0
				var actual: bool = space.ray_intersects(from, to, mask, query.hit_from_inside, query.hit_back_faces)
				var expected: bool = not space.intersect_ray(query).is_empty()
				assert_eq(actual, expected, "Boolean policy remains exact in clutter, inside starts and zero-length rays")

func test_native_boolean_ray_preserves_masks_inside_and_area_behavior():
	var world := RayWorld.new()
	add_child_autofree(world)
	var box := BoxShape3D.new()
	box.size = Vector3(2,2,2)
	for layer in [1,8]:
		var body := StaticBody3D.new()
		body.collision_layer = layer
		var collision := CollisionShape3D.new()
		collision.shape = box
		body.add_child(collision)
		world.add_child(body)
		body.position = Vector3(100,10,float(layer)*4.0)
	var area := Area3D.new()
	area.collision_layer = 1
	var area_collision := CollisionShape3D.new()
	area_collision.shape = box
	area.add_child(area_collision)
	world.add_child(area)
	area.position = Vector3(100,10,60)
	var mesh_body := StaticBody3D.new()
	var mesh_collision := CollisionShape3D.new()
	var triangle := ConcavePolygonShape3D.new()
	triangle.set_faces(PackedVector3Array([Vector3(100,9,69),Vector3(100,11,69),Vector3(100,10,71)]))
	mesh_collision.shape = triangle
	mesh_body.add_child(mesh_collision)
	world.add_child(mesh_body)
	await wait_physics_frames(2)
	var space = world.get_world_3d().direct_space_state
	assert_true(space.has_method("ray_intersects"),"Custom engine exposes the boolean wrapper")
	if not space.has_method("ray_intersects"): return
	var face_results: Array[bool] = []
	for backwards in [false,true]:
		var from := Vector3(104 if backwards else 96,10,70)
		var to := Vector3(96 if backwards else 104,10,70)
		for back_faces in [false,true]:
			var query := PhysicsRayQueryParameters3D.create(from,to,1)
			query.hit_back_faces = back_faces
			var expected: bool = not space.intersect_ray(query).is_empty()
			face_results.append(expected)
			assert_eq(space.ray_intersects(from,to,1,false,back_faces),expected,"Concave face orientation retains the requested backface policy")
	assert_true(face_results.has(true) and face_results.has(false),"Fixture exercises both allowed and rejected triangle faces")
	for z in [4.0,32.0,60.0,80.0]:
		var default_from := Vector3(96,10,z)
		var default_to := Vector3(104,10,z)
		var default_query := PhysicsRayQueryParameters3D.create(default_from,default_to)
		assert_eq(space.ray_intersects(default_from,default_to),not space.intersect_ray(default_query).is_empty(),"Binding defaults retain the standard ray policy")
		for inside in [false,true]:
			var from := Vector3(100 if inside else 96,10,z)
			var to := Vector3(104,10,z)
			for mask in [0,1,8,9]:
				for back_faces in [false,true]:
					var query := PhysicsRayQueryParameters3D.create(from,to,mask)
					query.hit_from_inside = inside
					query.hit_back_faces = back_faces
					assert_eq(space.ray_intersects(from,to,mask,inside,back_faces),not space.intersect_ray(query).is_empty(),"Native backend hit semantics remain identical")
	var combat := ArenaCombat.new(world)
	for z in [4.0,32.0,60.0,80.0]:
		combat.native_clear_rays = false
		var reference := combat.clear(Vector3(96,10,z),Vector3(104,10,z))
		combat.native_clear_rays = true
		assert_eq(combat.clear(Vector3(96,10,z),Vector3(104,10,z)),reference,"Map-only visibility retains its original mask and flags")
