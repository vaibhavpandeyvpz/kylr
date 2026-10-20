extends GutTest

func fixture(phase: String) -> ArenaMatch:
	var game:=ArenaMatch.new()
	game.map_id="faceoff";game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_physics_process(false)
	game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause();game.map.start_loadout()
	game.phase=phase
	game.authority=true
	game.countdown=3.5
	var robot:=game.add_robot(0,"Reload",0,true,"projector") as ArenaRobot
	robot.set_physics_process(false);robot.set_process(false)
	game.map.spawns=game.map.spawns.filter(func(spawn):return not spawn.get("stasis",false)).slice(0,1)
	game.spawn_robot(robot)
	robot.spawn_remaining=0.01
	return game

func test_respawn_plays_reload_once_without_consuming_ammunition_or_protection():
	var game:=await fixture("Active")
	var robot:ArenaRobot=game.robots[0]
	var inventory:=robot.ammo_inventory.duplicate(true)
	robot._physics_process(0.02)
	assert_eq(robot.anim_state,"pistol/reload")
	assert_eq(robot.spawn_reload_remaining,2.0)
	assert_eq(robot.reload_time,0.0,"Spawn presentation is not an ammunition reload")
	assert_eq(robot.protection,5.0)
	assert_almost_eq(robot.animator.current_animation_length/robot.animator.speed_scale,2.0,0.001)
	for step in 22:
		robot._physics_process(0.1)
		robot.update_aim_pose(0.1)
	assert_eq(robot.spawn_reload_remaining,0.0)
	assert_ne(robot.anim_state,"pistol/reload","Reload finishes once, rather than looping throughout immunity")
	assert_gt(robot.protection,2.7,"The rest of the five-second protection remains")
	assert_false(robot.can_act())
	assert_eq(robot.ammo_inventory,inventory)
	assert_eq(robot.reload_time,0.0)
	game.spawn_robot(robot)
	robot.spawn_remaining=0.01
	robot._physics_process(0.02)
	assert_eq(robot.spawn_reload_remaining,2.0,"A later respawn plays its own reload")

func test_opening_reload_fits_the_remaining_countdown():
	var game:=await fixture("Countdown")
	var robot:ArenaRobot=game.robots[0]
	robot._physics_process(0.02)
	assert_eq(robot.anim_state,"pistol/reload")
	assert_almost_eq(robot.spawn_reload_remaining,1.5,0.001)
	assert_almost_eq(robot.animator.current_animation_length/robot.animator.speed_scale,1.5,0.001)
	for step in 16:
		robot._physics_process(0.1)
		robot.update_aim_pose(0.1)
	assert_eq(robot.spawn_reload_remaining,0.0)
	assert_eq(robot.reload_time,0.0)
	assert_eq(game.phase,"Countdown")

func test_online_snapshot_preserves_spawn_reload_without_changing_ammo_reload():
	var game:=await fixture("Active")
	var robot:ArenaRobot=game.robots[0]
	robot._physics_process(0.02)
	var state:=robot.network_state()
	var remote:=game.add_robot(1,"Remote",1,false,"projector") as ArenaRobot
	remote.set_physics_process(false);remote.set_process(false)
	remote.restore_network(state)
	remote.update_aim_pose(0.1)
	assert_eq(remote.anim_state,"pistol/reload")
	assert_eq(remote.spawn_reload_remaining,2.0)
	assert_eq(remote.reload_time,0.0)
	assert_almost_eq(remote.animator.current_animation_length/remote.animator.speed_scale,2.0,0.001)
	state.spawn_reload=0.5
	remote.restore_network(state)
	assert_almost_eq(remote.animator.current_animation_position,remote.animator.current_animation_length*0.75,0.001,"Late snapshots join the remaining animation instead of restarting it")

func test_gun_game_keeps_its_assigned_weapon_and_skips_pistol_presentation():
	var game:=await fixture("Active")
	var robot:ArenaRobot=game.robots[0]
	game.match_type="GUNGAME"
	robot.gun_game_weapon="rocket_launcher"
	game.spawn_robot(robot)
	robot.spawn_remaining=0.01
	robot._physics_process(0.02)
	assert_eq(robot.equipped,"rocket_launcher")
	assert_eq(robot.spawn_reload_remaining,0.0)
	assert_eq(robot.reload_time,0.0)
	assert_eq(robot.protection,5.0)
