extends SceneTree
## Concurrent mixer/routing stress. The generated PCM is silent.
## Use the threaded Dummy audio driver for an independent headless control.

var output := ""
var seconds := 20.0
var routes: Array[int] = []
var changes := 0
var mixer_wraps := 0
var previous_mix_age := 0.0
var started := 0
var original_bus_count := 0
var player: AudioStreamPlayer

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):output=argument.trim_prefix("--output=")
		if argument.begins_with("--seconds="):seconds=float(argument.trim_prefix("--seconds="))
	run.call_deferred()

func add_bus(bus_name: String) -> int:
	AudioServer.add_bus()
	var index := AudioServer.bus_count-1
	AudioServer.set_bus_name(index,bus_name)
	return index

func run() -> void:
	if not output.is_absolute_path() or FileAccess.file_exists(output) or seconds<5 or seconds>60:
		push_error("Pass a fresh absolute --output and --seconds between 5 and 60")
		quit(2);return
	original_bus_count=AudioServer.bus_count
	add_bus("RouteTarget")
	for index in 32:
		routes.append(add_bus("RouteStress%d"%index))
	var pcm := AudioStreamWAV.new()
	pcm.format=AudioStreamWAV.FORMAT_16_BITS
	pcm.mix_rate=48000
	pcm.loop_mode=AudioStreamWAV.LOOP_FORWARD
	pcm.loop_end=4800
	var silence := PackedByteArray()
	silence.resize(9600)
	silence.fill(0)
	pcm.data=silence
	player=AudioStreamPlayer.new()
	player.stream=pcm
	player.bus="RouteStress0"
	root.add_child(player)
	player.play()
	await create_timer(0.1).timeout
	started=Time.get_ticks_usec()
	while Time.get_ticks_usec()-started<int(seconds*1000000.0):
		# Alternate valid and missing targets; both must fall back safely.
		# Changing a shared routing name between has() and operator[] must
		# never insert a null bus into the mixer's lookup table.
		for iteration in 2048:
			AudioServer.set_bus_send(routes[iteration%32],&"RouteTarget" if (iteration/32)%2==0 else &"MissingTarget")
			changes+=1
		var mix_age := AudioServer.get_time_since_last_mix()
		if mix_age<previous_mix_age:mixer_wraps+=1
		previous_mix_age=mix_age
		await process_frame
	player.stop()
	player.queue_free()
	await create_timer(0.1).timeout
	for index in range(AudioServer.bus_count-1,original_bus_count-1,-1):AudioServer.remove_bus(index)
	var passed := changes>=50000 and mixer_wraps>=3 and AudioServer.bus_count==original_bus_count
	var report := {"passed":passed,"seconds":(Time.get_ticks_usec()-started)/1000000.0,"route_changes":changes,"mixer_wraps":mixer_wraps,"bus_count_restored":AudioServer.bus_count==original_bus_count,"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),"probe_sha256":FileAccess.get_sha256(get_script().resource_path),"performance_acceptance":false,"audible_quality_acceptance":false}
	var file := FileAccess.open(output,FileAccess.WRITE)
	if file==null:push_error("Cannot write report");quit(2);return
	file.store_string(JSON.stringify(report,"\t"))
	print("AUDIO_BUS_ROUTE_STRESS ",JSON.stringify(report))
	quit(0 if passed else 1)
