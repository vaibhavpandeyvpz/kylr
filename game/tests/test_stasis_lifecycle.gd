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
