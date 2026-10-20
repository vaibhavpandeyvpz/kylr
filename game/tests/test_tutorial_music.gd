extends GutTest

class MusicApp extends Node:
	var match_node: ArenaMatch

func test_normalized_music_plays_audibly_and_crossfades_without_changing_user_volume():
	var app:=MusicApp.new()
	add_child_autofree(app)
	var music:=ArenaMusic.new()
	music.app=app
	add_child_autofree(music)
	var bus:=AudioServer.get_bus_index("Music")
	var user_gain:=AudioServer.get_bus_volume_db(bus)
	music._process(1.0)
	assert_true(music.beds[music.active].playing)
	assert_eq(music.state,"lobby")
	assert_eq(music.beds[music.active].volume_db,0.0,"Normalized music needs no extra -18 dB cut")
	music.transition("assembly")
	music._process(0.0)
	assert_lt(music.fade,1.0)
	music.accent("capture_stinger")
	assert_true(music.stinger.playing)
	assert_eq(music.stinger.volume_db,0.0)
	assert_eq(AudioServer.get_bus_volume_db(bus),user_gain,"Playback gain must preserve the Music slider")

func test_tutorial_uses_saved_controls_pauses_and_persists_completion():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autoqfree(game)
	await wait_physics_frames(3)
	game.phase = "Active"
	game.match_type = "TDM"
	game.local_robot = game.add_robot(1,"Learner",1,true,"raptor")
	game.local_robot.protection = 0
	var prefs := Preferences.new("user://tutorial-music-test.cfg")
	prefs.values.tutorial_hints = true
	prefs.bindings.fire = KEY_F
	prefs.bindings.reload = KEY_R
	var hints := TutorialHints.new()
	assert_string_contains(hints.text(game,prefs,0.1),"Team B")
	game.local_robot.protection = 2
	assert_eq(hints.text(game,prefs,20),"")
	assert_almost_eq(hints.clock,0.1,0.001)
	game.local_robot.protection = 0
	assert_string_contains(hints.text(game,prefs,8),"Fire: F")
	assert_eq(hints.text(game,prefs,40),"")
	assert_false(prefs.values.tutorial_hints)
	assert_false(Preferences.new(prefs.storage_path).values.tutorial_hints)
	DirAccess.remove_absolute(prefs.storage_path)

func test_music_pressure_tracks_objective_clock_and_warning_without_missing_audio():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autoqfree(game)
	await wait_physics_frames(3)
	game.match_type = "CTF"
	game.goal = 20
	game.time_limit = 900
	game.phase = "Active"
	assert_eq(ArenaMusic.intensity(game),0.0)
	game.flags[0].state = "carried"
	assert_eq(ArenaMusic.intensity(game),0.75)
	game.map.event_warned = true
	assert_eq(ArenaMusic.intensity(game),0.8)
	game.elapsed = 850
	assert_eq(ArenaMusic.intensity(game),1.0)
	game.phase = "Finished"
	assert_eq(ArenaMusic.intensity(game),0.0)
	var music := ArenaMusic.new()
	add_child_autoqfree(music)
	music.catalog.lobby = ""
	assert_null(music.stream("lobby"),"Missing authored music produces silence")
	music.catalog.lobby = "res://assets/audio/world/repair_ready.wav"
	var bed := music.stream("lobby",true) as AudioStreamWAV
	assert_not_null(bed)
	assert_eq(bed.loop_mode,AudioStreamWAV.LOOP_FORWARD)
	assert_gt(bed.loop_end,0)
	music.catalog.lobby = "res://assets/audio/music/lobby.ogg"
	music.transition("lobby")
	assert_true(music.beds[music.active].playing)
	music.shutdown()
	assert_false(music.is_processing())
	for player in music.beds + [music.pressure,music.stinger]:
		assert_false(player.playing)
		assert_null(player.stream)
