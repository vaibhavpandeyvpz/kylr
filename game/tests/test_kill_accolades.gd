extends GutTest

func test_ten_second_chain_thresholds_and_timeout():
	var game:=ArenaMatch.new()
	autofree(game)
	var robot:=ArenaRobot.new()
	autofree(robot)
	robot.robot_id=17
	game.local_robot=robot
	watch_signals(game)
	for count in 7:
		game.elapsed=count*10.0
		game.record_elimination(robot,"Rival")
		var event: Dictionary=get_signal_parameters(game,"local_elimination",count)[0]
		assert_eq(event.count,count+1)
		assert_eq(event.accolade,ArenaMatch.KILL_ACCOLADES.get(count+1,""))
	game.elapsed+=10.001
	game.record_elimination(robot,"Next rival")
	assert_eq(game.kill_chains[17].count,1)
	assert_eq(get_signal_parameters(game,"local_elimination",7)[0].accolade,"")

func test_server_targets_the_killer_and_client_filters_other_players():
	var game:=ArenaMatch.new()
	autofree(game)
	var robot:=ArenaRobot.new()
	autofree(robot)
	robot.robot_id=23
	game.local_robot=robot
	game.replicating=true
	watch_signals(game)
	game.record_elimination(robot,"Rival")
	assert_signal_not_emitted(game,"local_elimination")
	assert_eq(game.presentation_events.size(),1)
	var event: Dictionary=game.presentation_events[0]
	assert_eq(event.recipient,23)
	game.receive_elimination(event.merged({"recipient":24},true))
	assert_signal_not_emitted(game,"local_elimination")
	game.receive_elimination(event)
	assert_signal_emit_count(game,"local_elimination",1)

func test_caption_replaces_expires_and_preserves_literal_names():
	var caption:=KillAccolade.new()
	add_child_autofree(caption)
	caption.announce({"victim":"[b]Rival[/b]","accolade":"Double Kill","count":2})
	assert_eq(caption.victim,"[b]Rival[/b]")
	caption._process(0.2)
	caption.announce({"victim":"Next","accolade":"Triple Kill","count":3})
	assert_eq(caption.victim,"Next")
	assert_eq(caption.remaining,KillAccolade.HOLD)
	caption._process(3.0)
	assert_eq(caption.remaining,0.0)

func test_death_resets_chain_and_posthumous_kills_do_not_build_one():
	var game:=ArenaMatch.new()
	game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority=false
	var victim: ArenaRobot=game.add_robot(0,"Victim",0,true,"projector")
	var killer: ArenaRobot=game.add_robot(1,"Killer",1,true,"sentinel")
	game.local_robot=killer
	game.phase="Active"
	victim.global_position=Vector3(0,2,0)
	victim.last_safe=victim.global_position
	killer.global_position=Vector3(2,2,0)
	game.kill_chains[0]={"count":5,"time":0.0}
	game.kill_chains[1]={"count":1,"time":0.0}
	watch_signals(game)
	game.eliminate(victim,killer,"rifle")
	assert_false(game.kill_chains.has(0),"A real death clears the victim's chain")
	assert_eq(get_signal_parameters(game,"local_elimination",0)[0].accolade,"Double Kill")
	var announcements: Array=game.audio.events.filter(func(event): return event.get("asset","")=="speech/announcer/double_kill")
	assert_eq(announcements.size(),1,"An accepted award starts its actual recording once")
	assert_true(game.audio.last_started_voice.local,"Accolades are not world-positioned speech")
	assert_eq(game.audio.last_started_voice.profile.bus,"Announcer")
	game.local_robot=victim
	game.record_elimination(victim,"Posthumous target")
	game.record_elimination(victim,"Another posthumous target")
	assert_false(game.kill_chains.has(0),"Dead robots cannot start a new chain")
	assert_eq(get_signal_parameters(game,"local_elimination",2)[0].count,1)

func test_every_accolade_has_a_nonspatial_announcer_recording():
	var bank: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://data/audio/speech.json"))
	for title in ArenaMatch.KILL_ACCOLADES.values():
		var recording:=ArenaSpeech.recording(bank,title,true,-1)
		assert_eq(recording.bus,"Announcer")
		assert_eq(recording.gain,-8.0)
		var stream: AudioStream=load("res://assets/audio/"+recording.asset+".wav")
		assert_gt(stream.get_length(),0.4)
