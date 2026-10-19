extends GutTest

class ViewProbe extends Node3D:
	var alive := true
	var protection := 0.0
	var spawn_remaining := 0.0
	var repair = null
	var weapon_pose_visible := true
	var body := Node3D.new()
	var gun := Node3D.new()
	func _init():
		add_child(body)
		add_child(gun)

func test_camera_weapon_and_full_robot_are_mutually_exclusive_in_every_view():
	var game := ArenaMatch.new()
	autofree(game)
	var robot := ViewProbe.new()
	game.add_child(robot)
	game.local_robot = robot
	game.first_person = FirstPersonRig.new()
	game.add_child(game.first_person)
	game.phase = "Active"
	game.update_view_models()
	assert_true(game.first_person.visible)
	assert_false(robot.body.visible)
	assert_false(robot.gun.visible)
	game.third_person = true
	game.update_view_models()
	assert_false(game.first_person.visible)
	assert_true(robot.body.visible)
	assert_true(robot.gun.visible)
	game.third_person = false
	for state in [{"protection": 5.0}, {"spawn_remaining": 1.0}, {"repair": {}}, {"alive": false}]:
		var key: String = state.keys()[0]
		var previous = robot.get(key)
		robot.set(key, state[key])
		game.update_view_models()
		assert_false(game.first_person.visible, key)
		assert_true(robot.body.visible, key)
		robot.set(key, previous)
	for phase in ["Countdown", "Finished"]:
		game.phase = phase
		game.update_view_models()
		assert_false(game.first_person.visible, phase)
		assert_true(robot.body.visible, phase)
	robot.weapon_pose_visible = false
	game.update_view_models()
	assert_false(robot.gun.visible, "An unarmed results pose cannot reveal the local world weapon")


func test_unarmed_result_poses_hide_weapon_and_restore_it_for_combat():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	var robot: ArenaRobot = game.add_robot(0, "Pilot", 0, true, "projector")
	game.local_robot = robot
	game.phase = "Finished"
	var weapon_colliders := robot.gun.find_children("*", "CollisionObject3D", true, false)
	assert_gt(weapon_colliders.size(), 0)
	for clip in [RobotClips.VICTORIES[0], "defeated", "common/idle"]:
		robot.pose(clip)
		game.update_view_models()
		assert_false(robot.weapon_pose_visible, clip)
		assert_false(robot.gun.visible, clip)
		for collider in weapon_colliders: assert_eq(collider.collision_layer, 0, clip)
	robot.pose("idle")
	game.update_view_models()
	assert_true(robot.weapon_pose_visible)
	assert_true(robot.gun.visible)
	for collider in weapon_colliders: assert_gt(collider.collision_layer, 0)

func test_camera_weapon_and_ammo_do_not_cast_world_shadows():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	var robot: ArenaRobot = game.add_robot(0, "Pilot", 0, true, "projector")
	game.local_robot = robot
	game.phase = "Active"
	robot.protection = 0.0
	var fp := FirstPersonRig.new()
	fp.robot = robot
	fp.camera = game.camera
	game.add_child(fp)
	fp._process(0.0)
	assert_not_null(fp.gun)
	for root: Node in [fp.gun]:
		var meshes: Array[Node] = root.find_children("*", "MeshInstance3D", true, false)
		assert_gt(meshes.size(), 0)
		for mesh in meshes:
			assert_eq(mesh.cast_shadow, GeometryInstance3D.SHADOW_CASTING_SETTING_OFF)

func test_camera_weapon_fits_screen_and_preserves_reload_machinery():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	var robot: ArenaRobot = game.add_robot(0, "Pilot", 0, true, "projector")
	game.local_robot = robot
	game.phase = "Active"
	robot.protection = 0.0
	var viewport := SubViewport.new()
	viewport.size = Vector2i(1280, 720)
	add_child_autofree(viewport)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	camera.position = Vector3(0, 50, 0)
	game.camera = camera
	var fp := FirstPersonRig.new()
	fp.robot = robot
	fp.camera = camera
	viewport.add_child(fp)
	for resolution in [Vector2i(1280, 720), Vector2i(720, 1280), Vector2i(1920, 1080)]:
		viewport.size = resolution
		for fov in [60.0, 90.0]:
			camera.fov = fov
			for id in Arsenal.WEAPONS:
				robot.equip(id)
				fp._process(0.0)
				var cropped := false
				for corner in 8:
					var pixel := camera.unproject_position(fp.gun.global_transform * fp.weapon_bounds.get_endpoint(corner))
					var normalized := pixel / Vector2(resolution)
					cropped = cropped or normalized.x > 1.0 or normalized.y > 1.0
					assert_between(normalized.x,.38,.80,id+" uses the middle region and its spacer margins")
				assert_true(cropped, id + " must emerge partially cropped from the bottom")
				var pivot := fp.weapon_bounds.get_center()
				assert_true((fp.gun.global_transform * pivot).is_equal_approx(camera.global_transform * fp.framing * pivot), id + " keeps the established placement")
				var pivot_pixel := camera.unproject_position(fp.gun.global_transform * pivot)
				assert_almost_eq(pivot_pixel.x / resolution.x, 0.5857142857, 0.0001, id + " is centered within the middle weapon region")
				var muzzle := Assets.socket(fp.gun, Arsenal.WEAPONS[id].muzzles[0])
				var muzzle_pixel := camera.unproject_position(muzzle.global_position)
				assert_true(Rect2(Vector2.ZERO, Vector2(resolution)).has_point(muzzle_pixel), "%s muzzle at %s FOV %s: %s" % [id, resolution, fov, muzzle_pixel])
				for depth in [3.0, 10.0, 40.0]:
					var aim := Vector3(0, 0, -depth)
					fp.gun.global_transform = camera.global_transform * fp.aimed_framing(aim)
					var expected := (camera.global_transform * aim - muzzle.global_position).normalized()
					assert_gt((-muzzle.global_basis.z.normalized()).dot(expected), 0.99999, "%s points at the center aim ray at %sm" % [id, depth])
	robot.equip("rifle")
	fp._process(0.0)
	var pinned := fp.framing
	var source := Assets.find(robot.gun, "Skeleton3D") as Skeleton3D
	var target := Assets.find(fp.gun, "Skeleton3D") as Skeleton3D
	var player := Assets.find(robot.gun, "AnimationPlayer") as AnimationPlayer
	Assets.play(robot.gun, "reload")
	assert_true(player.is_playing())
	for time in [0.2, 0.8, 1.4]:
		player.seek(time, true)
		source.force_update_all_bone_transforms()
		camera.position += Vector3(1, 2, 3)
		camera.rotation += Vector3(0.1, 0.2, 0)
		fp._process(0.0)
		var pivot := fp.weapon_bounds.get_center()
		assert_true((fp.gun.global_transform * pivot).is_equal_approx(camera.global_transform * pinned * pivot))
		for bone in target.get_bone_count():
			var source_id := source.find_bone(target.get_bone_name(bone))
			assert_true(target.get_bone_pose(bone).is_equal_approx(source.get_bone_pose(source_id)), target.get_bone_name(bone))
