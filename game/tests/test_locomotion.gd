extends GutTest

func test_powered_jumps_release_with_momentum_and_coast_under_map_gravity():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	var robot: ArenaRobot = game.add_robot(0,"Lift probe",0,false,"projector")
	robot.set_physics_process(false)
	var previous_peaks := {}
	for multiplier in [0.8, 1.0, 1.2, 1.5]:
		game.configure_gravity({"gravity_multiplier": multiplier})
		for base_height in [ArenaTuning.NORMAL_JUMP_HEIGHT, ArenaTuning.CHARGED_JUMP_HEIGHT, ArenaTuning.JUMP_PAD_HEIGHT]:
			robot.global_position = Vector3(0,100,0)
			robot.velocity = Vector3.ZERO
			var height: float = game.jump_release_height(base_height)
			var speed: float = ArenaTuning.JUMP_PAD_SPEED if base_height == ArenaTuning.JUMP_PAD_HEIGHT else sqrt(2.0*game.gravity*height)
			robot.begin_powered_jump(height, speed, base_height == ArenaTuning.JUMP_PAD_HEIGHT)
			var peak := robot.position.y
			var released := false
			for tick in 180:
				var was_powered := robot.lift_target != -INF
				robot.simulate_movement(1.0/60.0,false,true)
				peak = maxf(peak,robot.position.y)
				if was_powered and robot.lift_target == -INF:
					released = true
					assert_almost_eq(robot.velocity.y, speed, 0.0001, "Thrust handoff retains full vertical momentum")
				elif released and robot.velocity.y <= 0: break
			assert_true(released)
			assert_almost_eq(peak-100.0,height+speed*speed/(2.0*game.gravity),speed/60.0+0.02)
			if previous_peaks.has(base_height):
				assert_lt(peak,previous_peaks[base_height],"Higher gravity reduces the physically simulated apex")
			previous_peaks[base_height] = peak

func test_map_gravity_multiplier_is_applied_before_match_physics():
	var game := ArenaMatch.new()
	autofree(game)
	game.configure_gravity({"gravity_multiplier": 1.5})
	assert_eq(game.gravity_multiplier, 1.5)
	assert_almost_eq(game.gravity, ArenaTuning.GRAVITY * 1.5, 0.001)
	assert_almost_eq(game.jump_release_height(ArenaTuning.NORMAL_JUMP_HEIGHT),2.0/3.0,0.001)
	assert_almost_eq(game.jump_release_height(ArenaTuning.CHARGED_JUMP_HEIGHT),4.0/3.0,0.001)
	assert_almost_eq(sqrt(2.0 * game.gravity * game.jump_release_height(ArenaTuning.NORMAL_JUMP_HEIGHT)),sqrt(2.0 * ArenaTuning.GRAVITY * ArenaTuning.NORMAL_JUMP_HEIGHT),0.001,"Launch impulse remains independent of map gravity")

class StepProbe extends ArenaRobot:
	func _ready() -> void:
		set_process(false)
		collision_layer = 2
		collision_mask = 1
		floor_snap_length = ArenaTuning.STEP_HEIGHT
		var shape := CollisionShape3D.new()
		var capsule := CapsuleShape3D.new()
		capsule.radius = 0.32
		capsule.height = 1.72
		shape.shape = capsule
		shape.position.y = 0.86
		add_child(shape)

func test_clear_low_step_can_be_climbed():
	var floor := StaticBody3D.new()
	var floor_shape := CollisionShape3D.new()
	var floor_box := BoxShape3D.new()
	floor_box.size = Vector3(4, 0.2, 4)
	floor_shape.shape = floor_box
	floor_shape.position.y = -0.1
	floor.add_child(floor_shape)
	add_child_autofree(floor)
	var step := StaticBody3D.new()
	var step_shape := CollisionShape3D.new()
	var step_box := BoxShape3D.new()
	step_box.size = Vector3(0.8, 0.3, 1.0)
	step_shape.shape = step_box
	step_shape.position = Vector3(0.4, 0.15, 0)
	step.add_child(step_shape)
	add_child_autofree(step)
	var robot := StepProbe.new()
	robot.position = Vector3(-0.34, 0.01, 0)
	add_child_autofree(robot)
	await wait_physics_frames(2)
	robot.move_and_slide()
	robot.velocity = Vector3(6, 0, 0)
	assert_true(robot.try_step_up(1.0 / 60.0))
	assert_gt(robot.position.y, 0.2)
	robot.move_and_slide()
	if not robot.is_on_floor(): robot.apply_floor_snap()
	assert_gt(robot.position.y, 0.2)
	for frame in 10:
		if robot.is_on_floor(): break
		robot.velocity.y -= ArenaTuning.GRAVITY / 60.0
		robot.move_and_slide()
	assert_true(robot.is_on_floor())

func test_speeds_and_modifier_precedence():
	assert_eq(Locomotion.speed(false, false, 100, false), 6.0)
	assert_eq(Locomotion.speed(false, true, 100, false), 12.0)
	assert_eq(Locomotion.speed(true, true, 100, false), 3.0)
	assert_eq(Locomotion.speed(true, false, 100, false), 3.0)
	assert_eq(Locomotion.speed(false, true, 50, false), 6.0)
	assert_eq(Locomotion.speed(false, true, 50.01, false), 12.0)
	assert_eq(Locomotion.speed(false, true, 100, true), 3.0)
	assert_eq(Locomotion.speed(false, false, 100, true), 3.0)
	assert_eq(ArenaTuning.MAX_EP / ArenaTuning.EP_DRAIN_PER_SECOND, 100.0)
	assert_eq(Locomotion.footstep_rate(3.0), 1.0)
	assert_almost_eq(Locomotion.footstep_rate(6.0), 1.266667, 0.0001)
	assert_eq(Locomotion.footstep_rate(12.0), 1.8)

func test_ground_and_air_steering_have_distinct_response():
	var start := Vector3.ZERO
	var desired := Vector3.FORWARD
	var ground := Locomotion.horizontal_velocity(start, desired, 6.0, true, 1.0 / 60.0)
	var air := Locomotion.horizontal_velocity(start, desired, 6.0, false, 1.0 / 60.0)
	assert_gt(ground.length(), air.length())
	assert_eq(ground.y, 0.0)
	var stopping := Locomotion.horizontal_velocity(Vector3(4.5, 2.0, 0.0), Vector3.ZERO, 4.5, true, 1.0 / 60.0)
	assert_lt(stopping.x, 4.5)
	assert_eq(stopping.y, 2.0)

func test_walk_binding_migrates_saved_modifier_and_honors_new_binding():
	var config := ConfigFile.new()
	assert_eq(Preferences.read_bindings(config).walk, KEY_SHIFT)
	config.set_value("bindings", "sprint", KEY_CTRL)
	assert_eq(Preferences.read_bindings(config).walk, KEY_CTRL)
	assert_eq(Preferences.read_bindings(config).sprint, KEY_ALT)
	config.set_value("bindings", "walk", KEY_ALT)
	assert_eq(Preferences.read_bindings(config).walk, KEY_ALT)
