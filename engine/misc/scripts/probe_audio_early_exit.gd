extends SceneTree
## Synthetic looping PCM, immediate exit before the mixer retires playbacks.
func _initialize(): run.call_deferred()

func run():
	var players: Array[AudioStreamPlayer] = []
	for i in 16:
		var recording := AudioStreamWAV.new()
		recording.format = AudioStreamWAV.FORMAT_16_BITS
		recording.mix_rate = 8000
		recording.loop_mode = AudioStreamWAV.LOOP_FORWARD
		recording.loop_end = 8000
		var data := PackedByteArray()
		data.resize(16000)
		recording.data = data
		var player := AudioStreamPlayer.new()
		player.stream = recording
		root.add_child(player)
		player.play()
		players.append(player)
	var stop_first := "--stop-first" in OS.get_cmdline_user_args()
	if stop_first:
		for player in players: player.stop()
	print("AUDIO_EARLY_EXIT_READY players=", players.size(), " stopped=", stop_first)
	quit()
