extends GutTest

class SpawnMapProbe extends ArenaMap:
	var begins := 0
	func begin_spawn(_spawn: Dictionary,_robot: ArenaRobot) -> void:
		begins+=1

class SpawnAudioProbe extends ArenaAudio:
	func set_loop(_key: String,_cue: String,_position: Vector3,_enabled: bool,_local := false,_rate := 1.0) -> void:
		pass

class SpawnRobotProbe extends ArenaRobot:
	func _ready():
		set_process(false)
		set_physics_process(false)

func test_loading_holds_spawn_until_reveal_and_resumes_without_restarting():
	var game:=ArenaMatch.new()
	autofree(game)
	game.phase="Countdown"
	game.countdown=4.0
	game.loading_hold=true
	var map:=SpawnMapProbe.new()
	autofree(map)
	game.map=map
	game.audio=SpawnAudioProbe.new()
	autofree(game.audio)
	var robot:=SpawnRobotProbe.new()
	robot.arena_match=game
	robot.spawn_remaining=1.5
	robot.spawn_fixture={"team":0,"duration":3.0,"reveal_after":1.0,"mount":null}
	add_child_autofree(robot)
	for tick in 30:
		robot._physics_process(1.0/60.0)
	assert_eq(robot.spawn_remaining,1.5,"Loading cannot consume the spawn sequence")
	assert_false(robot.spawn_started)
	assert_eq(map.begins,0,"Loading cannot trigger fixture motion or its sound")
	game.loading_hold=false
	robot._physics_process(0.25)
	assert_true(robot.spawn_started)
	assert_eq(map.begins,1)
	assert_eq(robot.spawn_remaining,1.25)
	game.loading_hold=true
	robot._physics_process(0.5)
	assert_eq(robot.spawn_remaining,1.25)
	game.loading_hold=false
	robot._physics_process(0.25)
	assert_eq(robot.spawn_remaining,1.0)
	assert_eq(map.begins,1,"Resuming preparation never restarts the fixture")

func test_loading_preserves_full_countdown_before_control_begins():
	var game := ArenaMatch.new()
	autofree(game)
	game.phase = "Countdown"
	game.loading_hold = true
	# Preparation can take longer than the opening cinematic on slower devices.
	for tick in 600:
		game._physics_process(1.0 / 60.0)
	assert_eq(game.phase, "Countdown")
	assert_eq(game.countdown, 0.0, "Loading must not consume the visible countdown")
	assert_eq(game.elapsed, 0.0)
	game.loading_hold = false
	game._physics_process(4.9)
	assert_eq(game.phase, "Countdown", "The player receives the full countdown")
	game._physics_process(0.1)
	assert_eq(game.phase, "Active")
	assert_eq(game.elapsed, 0.0, "The match clock starts after the countdown")

func test_resuming_preparation_preserves_remaining_countdown():
	var game := ArenaMatch.new()
	autofree(game)
	game.phase = "Countdown"
	game._physics_process(2.0)
	game.loading_hold = true
	game._physics_process(10.0)
	assert_eq(game.countdown, 2.0)
	assert_eq(game.phase, "Countdown")
	game.loading_hold = false
	game._physics_process(2.9)
	assert_eq(game.phase, "Countdown")
	game._physics_process(0.1)
	assert_eq(game.phase, "Active")
