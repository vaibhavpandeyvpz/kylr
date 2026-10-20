class_name ArenaMusic
extends Node
var app
var catalog: Dictionary = {}
var beds: Array[AudioStreamPlayer] = []
var pressure: AudioStreamPlayer
var stinger: AudioStreamPlayer
var active := 0
var state := ""
var round_id := 0
var score := -1
var fade := 1.0

func shutdown():
	set_process(false)
	for player in beds + [pressure,stinger]:
		if is_instance_valid(player):
			player.stop()
			player.stream = null

func _exit_tree(): shutdown()

func _ready():
	catalog = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio/music.json"))
	ArenaMix.ensure_bus("Music")
	for index in 2:
		var player := AudioStreamPlayer.new()
		player.bus = "Music"
		add_child(player)
		beds.append(player)
	pressure = AudioStreamPlayer.new()
	stinger = AudioStreamPlayer.new()
	for player in [pressure,stinger]:
		player.bus = "Music"
		add_child(player)

static func intensity(game: ArenaMatch) -> float:
	if game == null or game.phase != "Active": return 0.0
	var pressure := 0.0
	if game.time_limit-game.elapsed <= 60: pressure = 1.0
	if game.map.event_warned and not game.map.event_done: pressure = maxf(pressure,0.8)
	if game.match_type == "CTF":
		for flag in game.flags:
			if flag.state != "home": pressure = maxf(pressure,0.75)
	var top := 0
	if MatchTypes.individual(game.match_type):
		for robot in game.robots: top = maxi(top,robot.kills)
	else: top = maxi(game.team_scores[0],game.team_scores[1])
	if game.goal-top <= 2: pressure = maxf(pressure,0.6)
	return pressure

func stream(key: String, looping := false) -> AudioStream:
	var path: String = catalog.get(key,"")
	if path == "" or not ResourceLoader.exists(path): return null
	var recording: AudioStream = load(path).duplicate()
	if looping and recording is AudioStreamWAV:
		recording.loop_mode = AudioStreamWAV.LOOP_FORWARD
		recording.loop_begin = 0
		recording.loop_end = int(recording.get_length()*recording.mix_rate)
	elif looping and (recording is AudioStreamOggVorbis or recording is AudioStreamMP3): recording.loop = true
	return recording

func transition(next: String):
	state = next
	active = 1-active
	beds[active].stop()
	beds[active].stream = stream(next,true)
	if beds[active].stream: beds[active].play()
	fade = 0.0
	pressure.stop()
	if next == "active":
		pressure.stream = stream("pressure",true)
		if pressure.stream: pressure.play()
	if next in ["victory","draw","canceled"]: accent(next+"_stinger")

func accent(key: String):
	var recording := stream(key)
	if recording == null: return
	stinger.stop()
	stinger.stream = recording
	stinger.volume_db = -12
	stinger.play()

func _process(dt: float):
	if app == null: return
	var game: ArenaMatch = app.match_node
	var next := "lobby"
	if game != null:
		if game.phase == "Countdown": next = "assembly"
		elif game.phase == "Active": next = "active"
		elif game.phase == "Finished": next = "canceled" if game.result.get("canceled",false) else "draw" if game.result.get("title","") == "Draw" else "victory"
	if game != null and round_id != game.get_instance_id(): round_id = game.get_instance_id(); score = -1
	if next != state: transition(next)
	fade = minf(1,fade+dt)
	beds[active].volume_db = -18+linear_to_db(maxf(fade,0.001))
	beds[1-active].volume_db = -18+linear_to_db(maxf(1-fade,0.001))
	if fade >= 1: beds[1-active].stop()
	pressure.volume_db = -20+linear_to_db(maxf(intensity(game),0.001))
	if game != null and next == "active":
		var total: int = game.team_scores[0]+game.team_scores[1]
		if game.match_type == "CTF" and score >= 0 and total > score: accent("capture_stinger")
		score = total
