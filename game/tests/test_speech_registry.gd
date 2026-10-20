extends GutTest

func test_ten_robot_voices_are_stable_across_listeners_and_rounds():
	var bank := {"announcer":{"flag_taken":"speech/announcer/flag_taken"},"robots":[]}
	for index in ArenaSpeech.ROBOT_VOICES:
		bank.robots.append({"pitch_scale":1.0,"lines":{"pickup":"speech/robot_%02d/pickup" % index,"power_low":"speech/robot_%02d/power_low" % index}})
	for index in ArenaSpeech.ROBOT_VOICES:
		var first := ArenaSpeech.recording(bank,"Rifle acquired",false,index)
		assert_eq(first.asset,"speech/robot_%02d/pickup" % index)
		assert_eq(ArenaSpeech.recording(bank,"Shield Core acquired",false,index+10).asset,first.asset)
		assert_eq(ArenaSpeech.recording(bank,"POWER / Below 50",true,index).bus,"Voices")
	assert_eq(ArenaSpeech.recording(bank,"Pilot99 took the flag",true,-1).asset,"speech/announcer/flag_taken")
	assert_eq(ArenaSpeech.recording(bank,"Unknown",true,-1),{})
	assert_eq(ArenaSpeech.recording({"robots":[]},"Rifle acquired",false,0),{})

func test_fallback_pitch_is_bounded_and_missing_recordings_stay_silent():
	var bank := {"robots":[]}
	for index in ArenaSpeech.ROBOT_VOICES: bank.robots.append({"pitch_scale":3.0,"lines":{"armor_hit":"speech/shared/armor_hit"}})
	assert_eq(ArenaSpeech.recording(bank,"Armor hit",false,9).pitch_scale,1.3)
	assert_eq(ArenaSpeech.recording(bank,"Repair complete / Exit station",false,9),{})

func test_bundled_recordings_cover_all_ten_distinct_voice_banks_and_music_states():
	var bank: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio/speech.json"))
	assert_eq(bank.robots.size(),10)
	var voice_ids: Dictionary = {}
	for robot in bank.robots:
		voice_ids[robot.voice_id] = true
		for key in ["armor_hit","pickup","repair_complete","power_low","power_critical"] + ArenaSpeech.KILL_QUIPS.keys():
			assert_true(ResourceLoader.exists("res://assets/audio/"+str(robot.lines[key])+".wav"),robot.id+" / "+key)
			assert_eq(ArenaSpeech.recording(bank,ArenaSpeech.KILL_QUIPS.get(key,key),false,bank.robots.find(robot)).asset,robot.lines[key])
	assert_eq(voice_ids.size(),10)
	for key in bank.announcer:
		assert_true(ResourceLoader.exists("res://assets/audio/"+str(bank.announcer[key])+".wav"),"announcer / "+key)
	var music: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio/music.json"))
	assert_eq(music.size(),11)
	for key in music: assert_true(ResourceLoader.exists(music[key]),"music / "+key)
