extends GutTest

func assembled_match(map_id := "skyfall") -> ArenaMatch:
	var game := ArenaMatch.new()
	game.map_id = map_id
	game.online = true
	game.match_type = "CTF"
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_process(false)
	game.set_physics_process(false)
	game.map.assembly.seek(ArenaMatch.MAP_ASSEMBLY_SECONDS, true)
	game.map.assembly.pause()
	game.map.start_loadout()
	game.phase = "Active"
	for flag in game.flags: game.reset_flag_home(flag)
	return game

func test_skyfall_flags_use_authored_rooftop_gizmos_and_capture_volumes():
	var game: ArenaMatch = await assembled_match("skyfall")
	await wait_physics_frames(3)
	for flag in game.flags: game.reset_flag_home(flag)
	for team in 2:
		var flag: Dictionary = game.flags[team]
		var expected := game.map.world_point(game.map.config.flag_bases[team])
		assert_almost_eq(flag.home, expected, Vector3.ONE * 0.001)
		assert_almost_eq(flag.point, expected, Vector3.ONE * 0.001)
		assert_eq(flag.capture_area.name, "SK_SkyfallFlagCaptureTrigger_" + ("A" if team == 0 else "B"))
		assert_eq(flag.capture_area.collision_layer, 0)
		assert_almost_eq(flag.base_effect.global_position, expected, Vector3.ONE * 0.001)
		var markers: Array = game.map.markers.filter(func(m): return m.role == "flag_base" and m.zone == ("A" if team == 0 else "B"))
		assert_eq(markers.size(), 1)
		assert_eq(markers[0].level, "roof")

func test_authored_bases_are_nonblocking_and_stay_visible_without_flags():
	var game: ArenaMatch = await assembled_match()
	await wait_physics_frames(2)
	for team in 2:
		var flag: Dictionary = game.flags[team]
		var area: Area3D = flag.capture_area
		assert_eq(area.name, "SK_SkyfallFlagCaptureTrigger_" + ("A" if team == 0 else "B"))
		assert_eq(area.collision_layer, 0)
		assert_eq(area.collision_mask, 2)
		assert_almost_eq(flag.home, game.map.world_point(game.map.config.flag_bases[team]), Vector3.ONE * 0.001)
		flag.state = "carried"
		flag.node.hide()
		assert_true(flag.base_effect.visible)
		var query := PhysicsRayQueryParameters3D.create(flag.home + Vector3(-1.5,0.05,0), flag.home + Vector3(1.5,0.05,0), 1)
		assert_true(game.get_world_3d().direct_space_state.intersect_ray(query).is_empty(), "Capture disc never becomes an obstacle")

func test_carrier_contact_scores_once_and_respects_height_home_and_eligibility():
	var game: ArenaMatch = await assembled_match()
	var robot = game.add_robot(0,"Carrier",0,false,Arsenal.HEADS[0])
	robot.set_process(false)
	robot.set_physics_process(false)
	robot.protection = 0
	robot.alive = true
	robot.carrying = 1
	var enemy: Dictionary = game.flags[1]
	enemy.state = "carried"
	enemy.carrier = robot.robot_id
	robot.global_position = game.flags[0].home + Vector3(0,0.25,0)
	await wait_physics_frames(3)
	game.tick_flags(0.016)
	assert_eq(game.team_scores[0], 0, "Passing above the 10 cm volume does not capture")
	robot.global_position = game.flags[0].home + Vector3(0.98,0,0.98)
	await wait_physics_frames(3)
	game.tick_flags(0.016)
	assert_eq(game.team_scores[0], 0, "The square's corner is outside the round trigger, even with capsule contact")
	robot.global_position = game.flags[0].home + Vector3(1.15,0,0)
	game.flags[0].state = "dropped"
	game.flags[0].point = game.flags[0].home + Vector3(4,0,0)
	await wait_physics_frames(3)
	assert_true(game.flags[0].capture_area.overlaps_body(robot), "Capsule edge contacts the authored disc")
	game.tick_flags(0.016)
	assert_eq(game.team_scores[0], 0, "Own flag must be home")
	game.reset_flag_home(game.flags[0])
	robot.protection = 5
	game.tick_flags(0.016)
	assert_eq(game.team_scores[0], 0, "Protected robots cannot capture")
	robot.protection = 0
	game.tick_flags(0.016)
	game.tick_flags(0.016)
	assert_eq(game.team_scores[0], 1)
	assert_eq(robot.captures, 1)
	assert_eq(robot.carrying, -1)
	assert_eq(enemy.state, "home")
	assert_true(game.flags[0].base_effect.visible)
