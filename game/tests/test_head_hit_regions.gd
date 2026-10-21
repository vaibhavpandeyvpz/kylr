extends GutTest

class HitOwner extends RefCounted:
	var head := "projector"
	var upper_body := "default"
	var hit_rids: Array[RID] = []

class RayWorld extends Node3D:
	var robots: Array = []

func test_only_equipped_head_collision_is_marked_as_headshot():
	for head_name in ["projector", "sentinel", "porthole", "raptor", "arachne"]:
		var owner := HitOwner.new()
		owner.head = head_name
		var visual := Assets.model("characters", "tensor")
		add_child_autofree(visual)
		CollisionRig.install(visual, "characters", "tensor", owner)
		var head_shapes := 0
		var body_shapes := 0
		for collision in visual.find_children("*", "StaticBody3D", true, false):
			if collision.get_meta("hit_region", "body") == "head":
				head_shapes += 1
				assert_true(String(collision.get_meta("hit_mesh", "")).to_lower().contains(head_name))
			else: body_shapes += 1
		assert_gt(head_shapes, 0, head_name + " has authored head collision")
		assert_gt(body_shapes, 0, head_name + " retains body collision")

func test_ray_preserves_the_hit_collision_object_and_region():
	var world := RayWorld.new()
	add_child_autofree(world)
	var owner := HitOwner.new()
	var head := StaticBody3D.new()
	head.collision_layer = 4
	head.set_meta("robot", owner)
	head.set_meta("hit_region", "head")
	world.add_child(head)
	var shape := CollisionShape3D.new()
	shape.shape = SphereShape3D.new()
	head.add_child(shape)
	await wait_physics_frames(2)
	var hit := ArenaCombat.new(world).ray(Vector3(0, 0, 2), Vector3.ZERO)
	assert_eq(hit.collider, owner)
	assert_eq(hit.hit_object, head)
	assert_eq(hit.hit_region, "head")

func test_compound_hit_body_preserves_gaps_metadata_and_self_exclusion():
	var skeleton := Skeleton3D.new()
	skeleton.add_bone("Root")
	add_child_autofree(skeleton)
	var attachment := BoneAttachment3D.new()
	attachment.bone_name = "Root"
	skeleton.add_child(attachment)
	var owner := HitOwner.new()
	var bodies: Array[StaticBody3D] = []
	for offset in [-1.0,1.0]:
		var shape := ConvexPolygonShape3D.new()
		var points := PackedVector3Array()
		for x in [-0.2,0.2]:
			for y in [-0.2,0.2]:
				for z in [-0.2,0.2]: points.append(Vector3(offset+x,y,z))
		shape.points = points
		bodies.append(CollisionRig.add_shape(attachment,shape,owner,"head","SK_TestHead",null if bodies.is_empty() else bodies[0]))
	assert_same(bodies[0],bodies[1],"Disconnected hulls share one body")
	assert_eq(bodies[0].get_child_count(),2,"Both convex hulls remain separate shapes")
	assert_eq(owner.hit_rids.size(),1,"Self exclusion contains the compound body's RID once")
	await wait_physics_frames(2)
	var space := skeleton.get_world_3d().direct_space_state
	for x in [-1.0,1.0]:
		var query := PhysicsRayQueryParameters3D.create(Vector3(x,0,2),Vector3(x,0,-2),4)
		var hit := space.intersect_ray(query)
		assert_false(hit.is_empty())
		assert_same(hit.collider,bodies[0])
		assert_same(hit.collider.get_meta("robot"),owner)
		assert_eq(hit.collider.get_meta("hit_region"),"head")
		assert_eq(hit.collider.get_meta("hit_mesh"),"SK_TestHead")
		query.exclude = owner.hit_rids
		assert_true(space.intersect_ray(query).is_empty(),"Both hulls exclude the firing robot")
	assert_true(space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(0,0,2),Vector3(0,0,-2),4)).is_empty(),"Grouping never fills the gap")
	skeleton.set_bone_pose_position(0,Vector3.UP*2)
	skeleton.force_update_all_bone_transforms()
	await wait_physics_frames(2)
	assert_false(space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(-1,2,2),Vector3(-1,2,-2),4)).is_empty(),"Compound hulls follow the live bone")
	assert_true(space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(-1,0,2),Vector3(-1,0,-2),4)).is_empty(),"Old bone position no longer blocks shots")
