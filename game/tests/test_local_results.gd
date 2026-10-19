extends GutTest

func test_odd_rosters_randomize_the_extra_team_and_remain_balanced():
	var game := ArenaMatch.new()
	var larger_teams := {}
	for seed_value in 30:
		game.rng.seed = seed_value
		for total in range(2,11):
			var teams := game.local_roster_teams(total)
			var a := teams.count(0)
			var b := teams.count(1)
			assert_eq(a + b,total)
			assert_lte(absi(a-b),1)
			assert_lte(maxi(a,b),5)
			if total % 2 == 1: larger_teams[0 if a > b else 1] = true
	assert_eq(larger_teams.size(),2,"Either team can receive the odd participant")
	game.free()

func test_preferences_restore_even_counts_and_choices_without_starting():
	var path := "user://local_flow_test.cfg"
	var config := ConfigFile.new()
	config.set_value("preferences","count",9)
	assert_eq(config.save(path),OK)
	var prefs := Preferences.new(path)
	assert_eq(prefs.values.count,10)
	assert_false(prefs.setup_notices.is_empty())
	prefs.values.name = "Saved.Pilot"
	prefs.values.type = 2
	prefs.values.difficulty = 3
	prefs.values.count = 4
	prefs.values.goal = 75
	prefs.values.minutes = 20
	assert_eq(prefs.save(),OK)
	var restored := Preferences.new(path)
	for key in ["name","type","difficulty","count","goal","minutes"]:
		assert_eq(restored.values[key],prefs.values[key])
	DirAccess.remove_absolute(path)

func test_ctf_results_freeze_team_capture_time_and_individual_assists():
	var game := ArenaMatch.new()
	game.online = true
	game.authority = false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_process(false)
	game.match_type = "CTF"
	var pilot = game.add_robot(0,"Pilot",0,true,"projector")
	pilot.set_physics_process(false)
	pilot.set_process(false)
	pilot.kills = 8
	pilot.assists = 3
	pilot.captures = 2
	pilot.reached = 17.0
	game.team_scores = [3,3]
	game.team_reached = [90.0,80.0]
	game.finish()
	assert_eq(game.result.title,"Team B wins")
	assert_eq(game.result.mvp,"Pilot")
	assert_eq(game.result.entries[0].assists,3)
	assert_eq(game.result.entries[0].reached,17.0)
	assert_eq(game.result.teams[1].score,3)
	assert_eq(game.result.teams[1].time,80.0)
	game.team_scores[1] = 99
	game.team_reached[1] = 100.0
	assert_eq(game.result.teams[1].score,3,"Result remains authoritative at finish")
	assert_eq(game.result.teams[1].time,80.0)

func test_local_name_validation_matches_the_entire_saved_value():
	for value in ["Pilot","Pilot.2","Robot_1","ABCDEFGHIJKLMNOPQRST"]:
		assert_true(Preferences.valid_name(value))
	for value in ["","Pilot\n","Pilot name","Pilot-1","ABCDEFGHIJKLMNOPQRSTU"]:
		assert_false(Preferences.valid_name(value))
