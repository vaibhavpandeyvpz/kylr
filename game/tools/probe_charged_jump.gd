extends SceneTree

func _initialize() -> void:
	call_deferred("probe")

func probe() -> void:
	var game := ArenaMatch.new()
	var args := OS.get_cmdline_user_args()
	if not args.is_empty(): game.map_id = args[0]
	game.online = true
	root.add_child(game)
	await physics_frame
	await physics_frame
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0, true)
	game.map.start_loadout()
	await physics_frame
	game.map.build_navigation()
	for spawn in game.map.spawns:
		Assets.play(spawn.node,"deploy")
		var lift_player := Assets.find(spawn.node,"AnimationPlayer") as AnimationPlayer
		lift_player.seek(104.0/30.0,true)
		lift_player.pause()
		var lift_skeleton := Assets.find(spawn.node,"Skeleton3D") as Skeleton3D
		lift_skeleton.force_update_all_bone_transforms()
	await physics_frame
	game.online = false
	game.phase = "Active"
	game.count = 2
	game.goal = 1000
	game.time_limit = 10000
	var candidate: Vector2i
	var found := false
	for edge in game.map.traversal.actions:
		if game.map.traversal.actions[edge] == "charged_jump":
			candidate=edge
			found=true
			break
	if not found:
		print("PROBE no charged edge")
		quit(1)
		return
	var source: Vector3=game.map.traversal.graph.get_point_position(candidate.x)
	var destination: Vector3=game.map.traversal.graph.get_point_position(candidate.y)
	var robot := game.add_robot(0,"Probe",0,false,"projector") as ArenaRobot
	robot.position=source+Vector3.UP*0.02
	robot.last_safe=robot.position
	robot.spawn_remaining=0
	robot.protection=0
	robot.collision_layer=2
	robot.brain.decision=999
	robot.brain.retarget=999
	robot.brain.goal=destination
	robot.brain.goal_kind="probe"
	robot.brain.path=[{"point":destination,"action":"charged_jump","from":source,"entry":Vector3.INF}]
	var max_charge:=0.0
	var max_height:=source.y
	var jumped:=false
	var landed:=false
	for frame in 360:
		await physics_frame
		max_charge=maxf(max_charge,robot.jump_charge)
		max_height=maxf(max_height,robot.position.y)
		if robot.airborne_from_jump: jumped=true
		if jumped and robot.is_on_floor() and robot.position.distance_to(destination)<1.5:
			landed=true
			break
	print("PROBE source=",source," target=",destination," max_charge=",max_charge," rise=",max_height-source.y," jumped=",jumped," landed=",landed," end=",robot.position)
	var passed := landed and max_charge>=1.9 and max_height-source.y>2.5
	game.phase="Finished"
	for voice in game.audio.voices: voice.stop()
	OS.delay_msec(100)
	game.queue_free()
	for frame in 3: await physics_frame
	quit(0 if passed else 1)
