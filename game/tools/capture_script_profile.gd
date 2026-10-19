extends SceneTree
## Loopback-only debugger receiver. Diagnostic debug timings are not release FPS.
var server := TCPServer.new()
var tcp: StreamPeerTCP
var packets := PacketPeerStream.new()
var started := Time.get_ticks_msec()
var recording := false
var signatures := {}
var frames: Array = []
var messages := {}
var errors: Array = []
var visual_frames: Array = []
var capture_visual := false
var capture_scripts := true
var output := "res://reports/script-profile.json"
var captures: Array = []
var timeout_ms := 180000

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument == "--visual": capture_visual = true
		if argument == "--visual-only":
			capture_visual = true
			capture_scripts = false
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		if argument.begins_with("--timeout="): timeout_ms=int(argument.trim_prefix("--timeout="))*1000
	Engine.max_fps = 60
	if server.listen(6018,"127.0.0.1") != OK:
		push_error("Cannot open profiler loopback listener")
		quit(1)
	print("PROFILE_LISTENING 6018")

func _process(_dt: float) -> bool:
	if tcp == null:
		if server.is_connection_available():
			tcp = server.take_connection()
			packets.stream_peer = tcp
	else:
		tcp.poll()
		while packets.get_available_packet_count()>0:
			var message = packets.get_var()
			if not message is Array or message.size()!=3: continue
			var kind: String = message[0]
			var data: Array = message[2]
			messages[kind] = int(messages.get(kind,0))+1
			if kind == "error": errors.append(data)
			if kind == "arena:profile_begin":
				# Godot reuses function IDs when profiling restarts. Keep each
				# capture's signatures with its frames, never remap earlier frames.
				if not frames.is_empty() or not visual_frames.is_empty():
					captures.append({"signatures":signatures.duplicate(),"frames":frames,"visual_frames":visual_frames})
				signatures.clear()
				frames=[]
				visual_frames=[]
				recording = true
				if capture_scripts: packets.put_var(["profiler:servers",message[1],[true,[512,true]]])
				if capture_visual: packets.put_var(["profiler:visual",message[1],[true,[]]])
			elif kind == "arena:profile_end":
				recording = false
				if capture_scripts: packets.put_var(["profiler:servers",message[1],[false]])
				if capture_visual: packets.put_var(["profiler:visual",message[1],[false]])
			elif kind == "servers:function_signature": signatures[str(data[1])] = data[0]
			elif kind == "servers:profile_frame" and recording: frames.append(data)
			elif kind == "visual:profile_frame" and recording: visual_frames.append(data)
		if tcp.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			save()
			return true
	if Time.get_ticks_msec()-started>timeout_ms:
		save()
		return true
	return false

func save() -> void:
	FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify({"signatures":signatures,"frames":frames,"visual_frames":visual_frames,"captures":captures,"messages":messages,"errors":errors}))
	print("SCRIPT_PROFILE frames=",frames.size()," functions=",signatures.size()," visual_frames=",visual_frames.size())
	server.stop()
