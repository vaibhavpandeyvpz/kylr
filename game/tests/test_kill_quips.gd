extends GutTest

func test_special_lines_require_the_actual_finishing_weapon():
	for weapon in Arsenal.WEAPONS.keys() + ["rifle_headshot","Fall off map","Energy depleted"]:
		var choices := ArenaSpeech.kill_quip_choices(weapon)
		assert_eq("Boom baby!" in choices,weapon in ["rocket_launcher","grenade_launcher"],weapon)
		assert_eq("Headshot!" in choices,weapon=="rifle_headshot",weapon)
		assert_true("Eat that!" in choices)

func fixture() -> ArenaMatch:
	var game := ArenaMatch.new()
	game.online=true
	game.replicating=true
	add_child_autofree(game)
	return game

func test_authority_chooses_one_line_per_kill_without_repeats_or_gameplay_rng():
	var game := fixture()
	await wait_physics_frames(3)
	var robot: ArenaRobot=game.add_robot(1,"Killer",0,true,"projector")
	game.callouts.frequency=2 # A server's preferences never suppress client events.
	var gameplay_seed := game.rng.state
	var previous := ""
	for index in 30:
		game.callouts.kill_quip(robot,"rifle_headshot")
		var event: Dictionary=game.presentation_events.back()
		assert_ne(event.text,previous)
		assert_true(event.text in ArenaSpeech.kill_quip_choices("rifle_headshot"))
		assert_eq(event.robot_id,1)
		assert_false(event.critical)
		previous=event.text
	assert_eq(game.presentation_events.size(),30)
	assert_eq(game.rng.state,gameplay_seed)
	robot.alive=false
	game.callouts.kill_quip(robot,"rocket_launcher")
	assert_eq(game.presentation_events.size(),30,"A dead killer cannot speak")

func test_client_speech_follows_the_speaker_and_respects_listener_preferences():
	var game := fixture()
	await wait_physics_frames(3)
	game.authority=false
	game.set_physics_process(false)
	var robot: ArenaRobot=game.add_robot(1,"Killer",0,true,"projector")
	robot.set_physics_process(false)
	game.local_robot=robot
	robot.global_position=Vector3(1,0,0)
	assert_true(game.callouts.publish("Eat that!","Killer",0,false,robot.eye(),-1,1))
	var first := game.audio.last_started_voice
	var first_serial := first.serial
	assert_false(first.local,"Even the local speaker uses a moving 3D source")
	assert_eq(first.profile.bus,"Voices")
	assert_eq(first.profile.gain,-8.0,"Robot dialogue has clear headroom above the music bed")
	var feed := HudKillFeed.active_events(game,true)
	assert_eq(feed[0].text,"Eat that!")
	assert_eq(feed[0].actor,"Killer")
	robot.global_position=Vector3(-4,0,2)
	robot.crouched=true
	game.audio._physics_process(0.01)
	assert_lt(first.point.distance_to(robot.eye()),0.001)
	assert_lt(first.player.global_position.distance_to(robot.eye()),0.001)
	assert_true(game.callouts.publish("Next!","Killer",0,false,robot.eye(),-1,1),"Rapid kills bypass ordinary bark cooldowns")
	assert_true(not first.active or first.serial!=first_serial,"A new quip replaces the same speaker's unfinished line")
	var live := game.audio.voices.filter(func(voice): return voice.active and voice.profile.get("kill_quip",false))
	assert_eq(live.size(),1)
	game.callouts.frequency=2
	assert_false(game.callouts.publish("Loser.","Killer",0,false,robot.eye(),-1,1))
	game.callouts.frequency=0
	assert_false(game.callouts.publish("Loser.","Distant",1,false,robot.eye()+Vector3.RIGHT*26,-1,2))
	for text in ["Let's go!","Finding energy core.","Emergency!"]:
		game.callouts._process(0.01)
		game.notice(text,robot)
		var voice := game.audio.last_started_voice
		assert_false(voice.local)
		assert_lt(voice.point.distance_to(robot.eye()),0.001)
		assert_eq(HudKillFeed.active_events(game,true)[0].text,text)
		assert_eq(voice.emitter.get_ref(),robot)

func test_random_voice_assignment_is_unique_in_a_roster_and_replicated():
	var game := fixture()
	await wait_physics_frames(3)
	var used := {}
	for index in 10:
		var robot: ArenaRobot=game.add_robot(index,"Pilot "+str(index),0,true,"projector")
		assert_between(robot.voice_variant,0,9)
		used[robot.voice_variant]=true
	assert_eq(used.size(),10,"A shuffled voice deck gives the roster ten distinct random voices")
	var actor: ArenaRobot=game.robots[0]
	var state := actor.network_state()
	var saved := actor.voice_variant
	actor.voice_variant=-1
	actor.restore_network(state)
	assert_eq(actor.voice_variant,saved)
	game.callouts.kill_quip(actor,"pistol")
	var event: Dictionary=game.presentation_events.back()
	assert_eq(event.voice_variant,saved)
	game.authority=false
	game.local_robot=actor
	game.callouts.publish("Next!",actor.display_name,actor.team,false,actor.eye(),-1,actor.robot_id,[],7)
	assert_eq(game.audio.last_started_voice.profile.asset,"speech/robot_07/next","An event carries the authoritative voice independently of local defaults")

func test_following_voice_detaches_safely_and_reuse_clears_its_anchor():
	var audio:=ArenaAudio.new()
	add_child_autofree(audio)
	var emitter:=Node3D.new()
	add_child(emitter)
	assert_true(audio.cue_following("rifle",Vector3(0,1,-2),emitter))
	var voice:=audio.last_started_voice
	emitter.free()
	audio._physics_process(0.01)
	assert_null(voice.emitter)
	assert_lt(voice.point.distance_to(Vector3(0,1,-2)),0.001)
	voice.stop()
	assert_null(voice.emitter)
