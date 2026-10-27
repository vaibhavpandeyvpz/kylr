extends GutTest

func test_stasis_opens_only_for_spawn_and_closes_once_after_door_sweep_is_clear():
	var game:=ArenaMatch.new();game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause();game.map.start_loadout()
	var spawn: Dictionary=game.map.spawns.filter(func(s):return s.action=="open")[0]
	var fixture: Dictionary=game.map.fixture_by_id(spawn.id)
	fixture.motion.set_physics_process(false)
	assert_false(fixture.open)
	assert_true(fixture.motion.channels.main.done)
	assert_eq(fixture.motion.channels.main.clip,"close")
	var robot:=game.add_robot(99,"StasisProbe",spawn.team,true,"projector") as ArenaRobot
	robot.set_physics_process(false);robot.spawn_fixture=spawn;robot.spawn_remaining=1.5
	robot.global_position=spawn.mount.global_position
	game.map.tick_stasis()
	assert_false(fixture.open,"Occupancy alone must never open an empty chamber")
	game.map.begin_spawn(spawn,robot)
	assert_true(fixture.open)
	assert_eq(fixture.motion.channels.main.clip,"open")
	fixture.motion.advance(2.0)
	game.map.tick_stasis()
	assert_true(fixture.open,"A spawn still in progress keeps the doorway open")
	robot.spawn_remaining=0
	robot.global_position=fixture.node.global_transform*Vector3(0,0.53,1.2)
	game.map.tick_stasis()
	assert_true(fixture.open,"The native swinging door must not close through a departing robot")
	robot.global_position=fixture.node.global_transform*Vector3(0,0.53,3)
	game.map.tick_stasis()
	assert_false(fixture.open)
	assert_false(fixture.close_pending)
	assert_eq(fixture.motion.channels.main.clip,"close")
	fixture.motion.advance(2.0)
	var closed_time: float=fixture.motion.channels.main.time
	game.map.tick_stasis()
	assert_eq(fixture.motion.channels.main.time,closed_time,"Empty-chamber ticks do not restart the close animation")
	game.map.begin_spawn(spawn,robot)
	assert_eq(fixture.motion.channels.main.clip,"open","The next authorized spawn can reopen it")

func test_all_chambers_keep_initial_and_respawn_facing_until_deployment_finishes():
	var checked:=0
	for map_id in ["faceoff","skyfall","ramparts"]:
		var game:=ArenaMatch.new()
		game.map_id=map_id;game.online=true;game.authority=false
		add_child_autofree(game)
		await wait_physics_frames(3)
		game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause();game.map.start_loadout()
		var chambers:=game.map.spawns.filter(func(spawn): return spawn.get("stasis",false))
		var robot:=game.add_robot(91,"FacingProbe",0,true,"projector") as ArenaRobot
		robot.set_physics_process(false);robot.set_process(false)
		for spawn in chambers:
			game.map.spawns=[spawn]
			robot.team=spawn.team
			var forward:Vector3=spawn.node.global_basis.z.normalized()
			for mode in ["DM","TDM","CTF"]:
				game.match_type=mode
				for life in 2:
					game.phase="Countdown" if life==0 else "Active"
					robot.yaw=-0.3;robot.pitch=0.4
					game.spawn_robot(robot)
					assert_true(robot.alive,spawn.id)
					assert_gt(robot.spawn_remaining,0.0)
					assert_gt(robot.aim_direction().dot(forward),0.9999,spawn.id+" view faces the door")
					assert_gt(robot.body.global_basis.z.normalized().dot(forward),0.9999,spawn.id+" body faces the door")
					var command:Dictionary={"move":Vector2.ZERO,"yaw":wrapf(robot.yaw+PI,-PI,PI),"pitch":0.5,"walk":false,"sprint":false,"crouch":false,"fire":false,"secondary":false,"held":false,"release":false,"jump":false,"reload":false,"slot":""}
					OnlineInput.apply(robot,command)
					assert_gt(robot.aim_direction().dot(forward),0.9999,"Online look cannot turn a deploying occupant")
					robot.spawn_remaining=0.0
					if life==0:
						OnlineInput.apply(robot,command)
						assert_gt(robot.aim_direction().dot(forward),0.9999,"Countdown retains the door-facing view")
					game.phase="Active"
					OnlineInput.apply(robot,command)
					assert_almost_eq(robot.yaw,float(command.yaw),0.0001,"Normal aiming resumes despite spawn protection")
					assert_almost_eq(robot.pitch,0.5,0.0001)
					checked+=1
	assert_eq(checked,84,"Fourteen chambers, three modes, initial spawn and respawn")

func test_all_skyfall_spawns_face_the_islands_on_admission_and_respawn():
	var game:=ArenaMatch.new();game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause();game.map.start_loadout()
	var spawns:Array=game.map.spawns.duplicate()
	assert_eq(spawns.size(),10)
	var robot:=game.add_robot(96,"IslandFacing",0,true,"projector") as ArenaRobot
	robot.set_physics_process(false);robot.set_process(false)
	for spawn in spawns:
		game.map.spawns=[spawn]
		var toward_island:=Vector3(-signf(spawn.point.x),0,0)
		for life in 2:
			game.phase="Countdown" if life==0 else "Active"
			game.spawn_robot(robot)
			assert_gt(robot.aim_direction().dot(toward_island),0.9999,spawn.id+" faces the islands")

func test_faceoff_spawn_pits_face_the_building_front_on_admission_and_respawn():
	var game:=ArenaMatch.new()
	game.map_id="faceoff";game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause();game.map.start_loadout()
	var spawns:=game.map.spawns.filter(func(spawn):return not spawn.get("stasis",false))
	assert_eq(spawns.size(),8)
	var robot:=game.add_robot(95,"FrontFacing",0,true,"projector") as ArenaRobot
	robot.set_physics_process(false);robot.set_process(false)
	for spawn in spawns:
		game.map.spawns=[spawn]
		robot.team=spawn.team
		var toward_front:=Vector3(-signf(spawn.point.x),0,-signf(spawn.point.z)).normalized()
		for life in 2:
			game.phase="Countdown" if life==0 else "Active"
			game.spawn_robot(robot)
			assert_gt(robot.aim_direction().dot(toward_front),0.9999,spawn.id+" view faces the building front")
			assert_gt(robot.body.global_basis.z.normalized().dot(toward_front),0.9999,spawn.id+" body faces the building front")

func test_local_mouse_look_is_ignored_only_during_stasis_deployment_and_countdown():
	if DisplayServer.get_name()=="headless":
		pending("Mouse capture requires a windowed display server")
		return
	var game:=ArenaMatch.new();game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause();game.map.start_loadout()
	var spawn:Dictionary=game.map.spawns.filter(func(item): return item.get("stasis",false))[0]
	game.map.spawns=[spawn]
	var robot:=game.add_robot(97,"LocalFacing",spawn.team,true,"projector") as ArenaRobot
	robot.set_physics_process(false);robot.set_process(false)
	game.local_robot=robot
	game.phase="Countdown"
	game.spawn_robot(robot)
	var application=load("res://scripts/core/app.gd").new()
	autofree(application)
	application.ui=ArenaUI.new()
	autofree(application.ui)
	application.ui.screen="match"
	application.match_node=game
	application.startup_complete=true
	application.prefs=Preferences.new("user://stasis_input_test.cfg")
	var mouse:=InputEventMouseMotion.new()
	mouse.relative=Vector2(100,100)
	Input.mouse_mode=Input.MOUSE_MODE_CAPTURED
	var front:float=robot.yaw
	application._unhandled_input(mouse)
	assert_almost_eq(robot.yaw,front,0.0001)
	assert_almost_eq(robot.pitch,0.0,0.0001)
	robot.spawn_remaining=0.0
	application._unhandled_input(mouse)
	assert_almost_eq(robot.yaw,front,0.0001,"Countdown keeps the chamber-facing view")
	game.phase="Active"
	application._unhandled_input(mouse)
	assert_ne(robot.yaw,front,"Active play permits mouse look")
	assert_ne(robot.pitch,0.0)
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
