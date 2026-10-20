class_name ArenaCallouts
extends Node
## Captions follow accepted match events, never a second perception system.
var game
var frequency := 0
var captions: Array[Dictionary] = []
var clock := 0.0
var robot_last: Dictionary = {}
var team_last: Dictionary = {}
var recent_line: Dictionary = {}
var speech: Dictionary = {}

func _process(dt: float):
	clock += dt
	captions = captions.filter(func(line): return line.expires > clock)

func publish(text: String, speaker := "Announcer", team := -1, critical := true, point := Vector3.INF, recipient := -1, robot_id := -1) -> bool:
	if game is ArenaMatch and game.replicating and game.authority:
		game.present({"kind":"caption","text":text,"speaker":speaker,"team":team,"critical":critical,"point":point,"recipient":recipient,"robot_id":robot_id})
		# Only global critical state belongs in a late-join snapshot. Live robot
		# captions are filtered by each listener's distance and preferences.
		if not critical or recipient >= 0: return true
	if not critical:
		if frequency == 2: return false
		if is_instance_valid(game) and is_instance_valid(game.local_robot) and point != Vector3.INF:
			if game.local_robot.global_position.distance_to(point) > 25.0: return false
		var interval := 16.0 if frequency == 1 else 8.0
		if clock-float(robot_last.get(speaker,-1000)) < interval or recent_line.get(speaker,"") == text: return false
		var times: Array = team_last.get(team,[])
		times = times.filter(func(time): return clock-float(time)<5.0)
		if times.size() >= (1 if frequency == 1 else 2): return false
		times.append(clock)
		team_last[team] = times
		robot_last[speaker] = clock
		recent_line[speaker] = text
	else:
		# Replace lower-priority captions rather than queue stale objective news.
		captions = captions.filter(func(line): return line.critical)
	var direction := ""
	if not critical and point != Vector3.INF and is_instance_valid(game) and is_instance_valid(game.local_robot):
		var delta: Vector3 = point-game.local_robot.global_position
		var local: Vector3 = delta.rotated(Vector3.UP,-game.local_robot.yaw)
		if delta.length() > 2: direction = " / " + ("right" if local.x>0 else "left")
	var identity := speaker + (" / Team " + ("A" if team == 0 else "B") if team >= 0 else "") + direction
	if critical: speaker = "Announcer"
	if critical:
		for i in range(captions.size()-1,-1,-1):
			if captions[i].critical: captions.remove_at(i)
	captions.append({"text":identity + ": " + text,"critical":critical,"expires":clock+4.0,"robot_feed":not critical or robot_id>=0,"speaker":speaker if not critical else identity.get_slice(" / ",0),"team":team,"utterance":text,"direction":direction})
	while captions.size() > 3: captions.pop_front()
	play_recording(text,critical,point,robot_id)
	return true

func play_recording(text: String, critical: bool, point: Vector3, robot_id := -1):
	if game is ArenaMatch and game.replicating and game.authority: return
	if speech.is_empty(): speech = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio/speech.json"))
	var recording := ArenaSpeech.recording(speech,text,critical,robot_id)
	if recording.is_empty() or game == null: return
	var active_speech := 0
	for voice in game.audio.voices:
		if not voice.active: continue
		if critical and voice.profile.bus == recording.bus: voice.stop()
		elif not critical and voice.profile.bus == "Voices": active_speech += 1
	if not critical and active_speech >= 2: return
	# Entries are audio-catalog asset IDs, matched only after listener filtering.
	var cue := "speech/"+str(recording.asset)
	AudioCues.profile(cue)
	AudioCues.profiles[cue] = {"asset":recording.asset,"bus":recording.bus,"gain":recording.get("gain",-14.0),"priority":95 if critical else 70,"limit":1 if critical else 2,"near":5,"far":25,"pitch":0.0,"pitch_scale":recording.pitch_scale}
	game.audio.cue(cue,Vector3.ZERO if point == Vector3.INF else point,critical or (game.local_robot != null and robot_id == game.local_robot.robot_id))

func caption_text() -> String:
	var lines: Array[String] = []
	for caption in captions: lines.append(caption.text)
	return "\n".join(lines)
