extends SceneTree
var transport: OnlineTransport
var joined := false
var generations: Array = []
var max_roster := 0
var moved := false
var damaged := false
var finished := false
var first_position := Vector3.ZERO
var error := ""
var max_shots := 0
var canceled := false
var initial_protection := 0.0
var diagnostic_deadline := 0
var network_only := OS.get_environment("KYLR_PROBE_NETWORK_ONLY") == "1"
var cosmetic_roster := -1
func _initialize(): run.call_deferred()
func run():
	transport = OnlineTransport.new()
	transport.name = "OnlineTransport"
	root.add_child(transport)
	transport.failed.connect(func(reason): error = reason)
	transport.admitted.connect(func(game):
		joined = true
		cosmetic_roster = -1
		generations.append(transport.generation)
		first_position = game.local_robot.position)
	transport.command_source = func(command):
		command.yaw = 0.0
		command.pitch = 0.0
		if transport.game.phase == "Active":
			command.move = Vector2(0,-1) if transport.game.elapsed < 3 else Vector2.ZERO
			command.fire = OS.get_environment("KYLR_PROBE_FIRE") == "1"
		return command
	transport.connect_match(JSON.parse_string(OS.get_environment("KYLR_PROBE_ASSIGNMENT")))
	var duration := float(OS.get_environment("KYLR_PROBE_SECONDS"))
	var deadline := Time.get_ticks_msec()+int(duration*1000)
	while Time.get_ticks_msec() < deadline and error == "":
		await physics_frame
		if joined and transport.game and not transport.building and transport.game.local_robot != null:
			if Time.get_ticks_msec() >= diagnostic_deadline:
				diagnostic_deadline = Time.get_ticks_msec()+5000
				print("CLIENT_HEALTH snapshot=",transport.last_snapshot," ack=",transport.last_ack," pending=",transport.unacked.size()," physics_frames=",Engine.get_physics_frames())
			if network_only and cosmetic_roster != transport.game.robots.size():
				trim_cosmetics(transport.game)
				cosmetic_roster = transport.game.robots.size()
			max_roster = maxi(max_roster,transport.game.robots.size())
			max_shots = maxi(max_shots,transport.game.local_robot.network_shots)
			canceled = canceled or transport.game.result.get("canceled",false)
			moved = moved or transport.game.local_robot.position.distance_to(first_position) > 1
			for robot in transport.game.robots: damaged = damaged or robot.ah < 99 or robot.deaths > 0
			finished = finished or transport.game.phase == "Finished"
	var result := {"network_only":network_only,"joined":joined,"generations":generations.size(),"max_roster":max_roster,"moved":moved,"damaged":damaged,"finished":finished,"error":error,"shots":max_shots,"canceled":canceled,"ack":transport.last_ack,"snapshot":transport.last_snapshot,"pending":transport.unacked.size()}
	var output := FileAccess.open(OS.get_environment("KYLR_PROBE_REPORT"),FileAccess.WRITE)
	output.store_string(JSON.stringify(result))
	print("ONLINE_CLIENT ",JSON.stringify(result))
	transport.close()
	transport.queue_free()
	await process_frame
	await process_frame
	quit(0 if joined and error == "" else 1)

func trim_cosmetics(node: Node):
	# Ten local processes qualify transport/server load separately from ten GPUs.
	# Do not change process_mode: that would remove CollisionObject3D bodies.
	node.set_process(false)
	node.set_physics_process(false)
	for child in node.get_children(): trim_cosmetics(child)
