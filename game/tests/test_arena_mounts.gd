extends GutTest

func test_night_arena_uses_shadowed_moonlight_with_readable_fill():
	# Construct the environment alone, without triggering map initialization.
	var world := ArenaMap.new()
	autofree(world)
	world.add_world()
	var directional_lights := world.find_children("*", "DirectionalLight3D", true, false)
	assert_eq(directional_lights.size(), 1)
	if directional_lights.size() != 1: return
	var moon := directional_lights[0] as DirectionalLight3D
	assert_eq(moon.name, "LGT_Key_Moon")
	assert_gt(moon.light_energy, 0.0)
	assert_lt(moon.light_energy, 0.3, "Moonlight stays well below the former 0.85 sunlight")
	assert_gt(moon.light_color.b, moon.light_color.r, "Moonlight has a cool tint")
	assert_true(moon.shadow_enabled, "Sheltered surfaces stay shaded")
	var environment := world.find_children("*","WorldEnvironment",true,false)[0] as WorldEnvironment
	assert_eq(environment.environment.ambient_light_source,Environment.AMBIENT_SOURCE_COLOR)
	assert_gt(environment.environment.ambient_light_energy,0.0)
	assert_lt(environment.environment.ambient_light_energy,0.3,"Fill retains directional contrast")
	assert_eq(environment.environment.reflected_light_source,Environment.REFLECTION_SOURCE_SKY)

func test_ground_ammo_uses_its_authored_collision_only_for_pickup_overlap():
	var mount := Node3D.new()
	add_child_autofree(mount)
	var arena := ArenaMap.new()
	autofree(arena)
	arena.pickup_fixture({"name":"ammo_test","position_godot":[0,0,0]}, mount, "ammo", "rifle")
	var fixture: Dictionary = arena.fixtures[0]
	var trigger: Area3D = fixture.trigger
	assert_not_null(trigger)
	assert_eq(trigger.collision_layer, 0)
	assert_eq(trigger.collision_mask, 2)
	assert_eq(fixture.payload.find_children("*", "StaticBody3D", true, false).size(), 0, "Ground pack cannot block movement")
	var shape := trigger.get_child(0) as CollisionShape3D
	assert_not_null(shape)
	if shape == null: return
	var center: Vector3 = shape.to_global(shape.shape.get_debug_mesh().get_aabb().get_center())
	var robot := CharacterBody3D.new()
	add_child_autofree(robot)
	robot.collision_layer = 2
	var robot_shape := CollisionShape3D.new()
	robot_shape.shape = SphereShape3D.new()
	robot_shape.shape.radius = 0.25
	robot.add_child(robot_shape)
	robot.global_position = center - Vector3.RIGHT * 0.5
	await wait_physics_frames(2)
	assert_null(robot.move_and_collide(Vector3.RIGHT), "The ammo pack cannot stop a robot moving through it")
	robot.global_position = center
	await wait_physics_frames(3)
	assert_true(trigger.overlaps_body(robot), "The pack mesh still detects a robot for pickup")
