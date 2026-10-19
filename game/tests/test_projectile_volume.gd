extends GutTest

class World extends Node3D:
	var robots: Array = []

class Target extends StaticBody3D:
	var alive := true
	var hit_rids: Array = []

func test_reused_sweep_exclusions_follow_shooter_death_and_respawn():
	var world := World.new()
	add_child_autofree(world)
	var combat := ArenaCombat.new(world)
	for distance in [2.0,4.0]:
		var target := Target.new()
		target.collision_layer = 0
		world.add_child(target)
		var hull := wall(world,Vector3(0,0,-distance),Vector3.ONE)
		hull.set_meta("robot",target)
		target.hit_rids.append(hull.get_rid())
		world.robots.append(target)
	await wait_physics_frames(2)
	var first: Target = world.robots[0]
	var second: Target = world.robots[1]
	for repeat in 3:
		assert_eq(combat.beam_hit(Vector3.ZERO,Vector3(0,0,-6),.1,[first.get_rid()]).collider,second)
	assert_eq(combat.beam_hit(Vector3.ZERO,Vector3(0,0,-6),.1,[second.get_rid()]).collider,first)
	first.alive = false
	assert_eq(combat.beam_hit(Vector3.ZERO,Vector3(0,0,-6),.1).collider,second)
	first.alive = true
	assert_eq(combat.beam_hit(Vector3.ZERO,Vector3(0,0,-6),.1).collider,first)
	# A replaced collider list must invalidate reuse even for the same shooter.
	first.hit_rids.clear()
	assert_eq(combat.beam_hit(Vector3.ZERO,Vector3(0,0,-6),.1,[first.get_rid()]).collider,first)

class Shot extends Node3D:
	var weapon := "rocket_launcher"
	var visual: Node3D
	var spin := 0.0

func test_compound_prefilter_preserves_exact_native_contacts():
	var world := World.new()
	add_child_autofree(world)
	var combat := ArenaCombat.new(world)
	wall(world,Vector3(0,0,-5),Vector3(.15,2,.01))
	var shot := Shot.new()
	world.add_child(shot)
	await wait_physics_frames(2)
	var hits := 0
	var misses := 0
	for weapon in ["rocket_launcher","grenade_launcher"]:
		shot.weapon = weapon
		for offset in [-1.0,-.1,0.0,.1,1.0]:
			shot.position = Vector3(offset,0,0)
			shot.spin = offset*2.0
			var motion := Vector3(0,0,-10)
			var expected := {}
			for component in ProjectileCollision.shapes(weapon):
				var hit := combat.sweep(component.shape,shot.global_transform*ProjectileCollision.local_pose(shot,component),motion)
				if not hit.is_empty() and (expected.is_empty() or hit.fraction<expected.fraction): expected=hit
			var actual := combat.projectile_hit(shot,motion)
			assert_eq(actual.is_empty(),expected.is_empty(),weapon+" contact classification")
			if expected.is_empty(): misses += 1
			else:
				hits += 1
				assert_eq(actual.collider,expected.collider)
				assert_almost_eq(float(actual.fraction),float(expected.fraction),.00001)
	assert_gt(hits,0)
	assert_gt(misses,0)

func wall(world: Node3D, at: Vector3, size: Vector3) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.collision_layer = 1
	var collider := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	collider.shape = box
	body.add_child(collider)
	world.add_child(body)
	body.position = at
	return body

func test_swept_body_hits_gap_edges_that_center_ray_misses():
	var world := World.new()
	add_child_autofree(world)
	var combat := ArenaCombat.new(world)
	wall(world,Vector3(-0.18,0,-5),Vector3(0.3,2,0.04))
	wall(world,Vector3(0.18,0,-5),Vector3(0.3,2,0.04))
	await wait_physics_frames(2)
	assert_true(combat.ray(Vector3.ZERO,Vector3(0,0,-10)).is_empty(),"Center ray fits through the 6 cm gap")
	assert_true(combat.beam_hit(Vector3.ZERO,Vector3(0,0,-10),0.02).is_empty(),"4 cm beam fits")
	var hit := combat.beam_hit(Vector3.ZERO,Vector3(0,0,-10),0.05)
	assert_false(hit.is_empty(),"10 cm orb hits the gap edge")
	assert_lt(float(hit.fraction),0.5)
	var thin_wall := wall(world,Vector3(0,0,-8),Vector3(3,3,0.01))
	await wait_physics_frames(1)
	hit = combat.beam_hit(Vector3.ZERO,Vector3(0,0,-100),0.02)
	assert_eq(hit.collider,thin_wall,"Long sweeps cannot tunnel through a thin wall")

func test_authored_collision_components_are_cached_and_have_volume():
	for weapon in ["rocket_launcher","grenade_launcher"]:
		var components := ProjectileCollision.shapes(weapon)
		assert_gt(components.size(),0)
		assert_same(components[0].shape,ProjectileCollision.shapes(weapon)[0].shape)
		for component in components:
			assert_true(component.shape is ConvexPolygonShape3D)
			assert_gt(component.shape.points.size(),3)
			assert_true(component.pose.is_finite())

func test_emissive_trails_are_not_damage_volumes():
	assert_almost_eq(ProjectileCollision.shapes("flak_cannon")[0].shape.radius,FlakRoundVisual.DEFAULT_DIAMETER_M/2.0,0.00001)
	assert_almost_eq(ProjectileCollision.shapes("lightning_gun")[0].shape.radius,Arsenal.ORB_DIAMETER/2.0,0.00001)
	assert_eq(ProjectileCollision.shapes("emp_gun")[0].shape.size,Vector3(.06,.06,.15))
