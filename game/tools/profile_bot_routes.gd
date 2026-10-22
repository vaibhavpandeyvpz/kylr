extends SceneTree

func _initialize() -> void:
	call_deferred("matrix" if OS.get_cmdline_user_args().has("--matrix") else "profile")

func matrix() -> void:
	var map_id := "faceoff"
	var directory := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--map="): map_id=argument.trim_prefix("--map=")
		if argument.begins_with("--report-directory="): directory=argument.trim_prefix("--report-directory=")
	if map_id not in ["faceoff","skyfall"] or not directory.begins_with("res://reports/roster/"):
		push_error("Choose a map and a report directory under res://reports/roster/");quit(1);return
	for mode in ["DM","TDM","CTF","ELIMINATION","GUNGAME"]:
		for count in [2,4,6,8,10]:
			var seconds := 120 if mode=="CTF" else 30
			var path := directory.path_join(mode.to_lower()+"-"+str(count)+".json")
			if FileAccess.file_exists(path): push_error("Roster report already exists: "+path);quit(1);return
			var arguments := PackedStringArray([mode,str(count),str(seconds),"normal","123",map_id,"1","--report-output="+path])
			for option in OS.get_cmdline_user_args():
				if option.begins_with("--decision-phases="): arguments.append(option)
			await profile(arguments,false)
			print("ROSTER_CASE_COMPLETE ",map_id," ",mode,"/",count)
	print("ROSTER_MATRIX_COMPLETE ",map_id)
	quit()

func profile(args: PackedStringArray=PackedStringArray(), exit_after := true):
	if args.is_empty(): args=OS.get_cmdline_user_args()
	var report_prefix := ""
	var report_output := ""
	for argument in args:
		if argument.begins_with("--report-output="):
			report_output=argument.trim_prefix("--report-output=").simplify_path()
			if not report_output.begins_with("res://reports/") or FileAccess.file_exists(report_output):
				push_error("Choose a fresh report path inside res://reports/")
				quit(1);return
		if argument.begins_with("--report-prefix="):
			report_prefix = argument.get_slice("=",1)
			if not report_prefix.is_valid_identifier():
				push_error("Diagnostic report prefix must be an identifier")
				quit(1)
				return
	for argument in args:
		if argument.begins_with("--decision-phases="):
			ArenaBrain.decision_phases = clampi(int(argument.get_slice("=",1)),1,16)
	var mode := String(args[0]).to_upper() if args.size() > 0 else "DM"
	var count := int(args[1]) if args.size() > 1 else 10
	var seconds := float(args[2]) if args.size() > 2 else 60.0
	if mode == "CTF": seconds = maxf(seconds, 120.0)
	var game := ArenaMatch.new()
	game.map_id = String(args[5]) if args.size()>5 else "skyfall"
	game.difficulty = int(args[6]) if args.size()>6 else 1
	game.online = true
	game.match_type = mode
	root.add_child(game)
	if args.size()>4: game.rng.seed=int(args[4])
	var match_seed := game.rng.seed
	var upper_floor_case := args.size()>7 and args[7]=="upper-floor"
	await physics_frame
	await physics_frame
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0, true)
	game.map.start_loadout()
	await physics_frame
	game.map.build_navigation()
	if args.size()>3 and args[3]=="trace":
		for spawn in game.map.spawns:
			print("SPAWN ",spawn.point," fixture=",spawn.node.global_position," mount_before=",spawn.mount.global_position)
	for spawn in game.map.spawns:
		Assets.play(spawn.node,spawn.action)
		var lift_player := Assets.find(spawn.node,"AnimationPlayer") as AnimationPlayer
		lift_player.seek(spawn.duration,true)
		lift_player.pause()
		var lift_skeleton := Assets.find(spawn.node,"Skeleton3D") as Skeleton3D
		lift_skeleton.force_update_all_bone_transforms()
	await physics_frame
	await physics_frame
	if args.size()>3 and args[3]=="trace":
		for spawn in game.map.spawns:
			print("SPAWN_AFTER ",spawn.point," mount=",spawn.mount.global_position)
	game.online = false
	game.phase = "Active"
	game.count = count
	game.goal = 1000
	game.time_limit = 10000
	var stats: Array = []
	for id in count:
		var team := id % 2
		var robot := game.add_robot(id, "Bot %d" % id, team, false, "projector") as ArenaRobot
		var spawn: Dictionary = game.map.spawns.filter(func(item): return item.team == team)[id / 2]
		robot.global_position = spawn.mount.global_position + Vector3.UP * 0.01
		robot.last_safe = robot.global_position
		robot.spawn_fixture = spawn
		robot.spawn_remaining = 0.0
		robot.protection = 0.0
		robot.collision_layer = 2
		robot.bot_aim = Vector3.FORWARD
		if mode=="GUNGAME": game.advance_gun_game(robot)
		if upper_floor_case:
			var lifts: Array=game.map.fixtures.filter(func(item): return item.has("lift_controller"))
			if id<lifts.size():
				var fixture: Dictionary=lifts[id]
				var corner := Vector3.INF
				var farthest := 0.0
				for node_id in game.map.traversal.graph.get_point_ids():
					var point: Vector3=game.map.traversal.graph.get_point_position(node_id)
					var local: Vector3=fixture.node.to_local(point)
					if absf(point.y-fixture.lift_controller.upper)>.1 or absf(local.x)>6.0 or absf(local.z)>6.5: continue
					var distance: float=point.distance_to(fixture.lift_controller.surface.global_position)
					if distance>farthest: farthest=distance;corner=point
				assert(corner!=Vector3.INF,"Upper-floor probe needs an actual clear interior corner")
				robot.global_position=corner
				robot.last_safe=corner
		stats.append({"id":id,"team":team,"start":robot.position,"roof_exit":false,"left_zone":false,"enemy_zone":false,"portal":0,"pad":0,"normal_jump":0,"charged_jump":0,"blocked_frames":0,"distance":0.0,"closest_enemy_flag":9999.0,"repair_visits":0,"repairing":false,"kinds":{},"last":robot.position,"lift":false,"jumping":false})
	var frame_times: Array[float] = []
	var physics_times: Array[float] = []
	var total_frames := roundi(seconds * 60.0)
	var started_usec := Time.get_ticks_usec()
	for frame in total_frames:
		await physics_frame
		if args.size()>3 and args[3]=="trace" and frame%60==0:
			for robot in game.robots:
				var step: Dictionary=robot.brain.path[robot.brain.path_index] if robot.brain and robot.brain.path_index<robot.brain.path.size() else {}
				print("TRACE ",frame/60," bot=",robot.robot_id," pos=",robot.position," input=",robot.move_input," goal=",robot.brain.goal_kind," target=",robot.brain.goal," step=",step," transition=",robot.brain.transition_index," launched=",robot.brain.transition_launched," jump_charge=",robot.jump_charge)
		if frame % 6 != 0: continue
		frame_times.append(Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0)
		physics_times.append(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0)
		for id in count:
			var robot: ArenaRobot = game.robots[id]
			var row: Dictionary = stats[id]
			if not robot.alive: continue
			if robot.equipped!=row.get("last_weapon","pistol"):
				row.weapon_switches=row.get("weapon_switches",0)+1
				row.last_weapon=robot.equipped
			if robot.pickup_weapon!="" and robot.pickup_weapon!=row.get("last_pickup",""):
				row.weapon_pickups=row.get("weapon_pickups",0)+1
			row.last_pickup=robot.pickup_weapon
			if robot.packs>int(row.get("last_packs",0)): row.ammo_pickups=row.get("ammo_pickups",0)+robot.packs-int(row.get("last_packs",0))
			row.last_packs=robot.packs
			if robot.reload_time>0 and not row.get("reloading",false): row.reloads=row.get("reloads",0)+1
			row.reloading=robot.reload_time>0
			var shot_delta: int = robot.network_shots-int(row.get("last_shots",0))
			if shot_delta>0 and robot.wants_secondary: row.secondary_shots=row.get("secondary_shots",0)+shot_delta
			row.last_shots=robot.network_shots
			var p: Vector3 = robot.position
			var previous: Vector3 = row.last
			var displacement: float = p.distance_to(previous)
			row.distance += displacement
			if displacement > 10.0 and absf(p.y-previous.y)>5.0: row.portal += 1
			if not row.roof_exit and row.start.y>=30 and p.y<29: row.roof_exit=true
			if upper_floor_case and row.start.y>3 and p.y<row.start.y-1.0 and not row.has("upper_floor_exit"):
				row["upper_floor_exit"]=robot.deaths==0
				row["upper_floor_exit_deaths"]=robot.deaths
				row["upper_floor_exit_elapsed"]=game.elapsed
			if absf(p.z)<10: row.left_zone=true
			if signf(p.z)!=signf(row.start.z) and absf(p.z)>10: row.enemy_zone=true
			if mode == "CTF": row.closest_enemy_flag = minf(row.closest_enemy_flag,p.distance_to(game.flags[1-robot.team].point))
			if robot.lift_from_pad and robot.lift_target>p.y and not row.lift: row.pad += 1
			row.lift=robot.lift_from_pad and robot.lift_target>p.y
			if robot.airborne_from_jump and not row.jumping:
				if robot.brain and robot.brain.path_index < robot.brain.path.size() and robot.brain.path[robot.brain.path_index].action == "charged_jump": row.charged_jump += 1
				else: row.normal_jump += 1
			row.jumping=robot.airborne_from_jump
			if robot.repair != null and not row.repairing: row.repair_visits += 1
			row.repairing = robot.repair != null
			if robot.brain:
				if robot.brain.target != null:
					row.combat_samples=row.get("combat_samples",0)+1
					if Vector2(p.x-previous.x,p.z-previous.z).length()>0.03: row.moving_combat=row.get("moving_combat",0)+1
					if absf(robot.move_input.x)>0.3: row.strafing=row.get("strafing",0)+1
					if robot.crouched: row.crouching=row.get("crouching",0)+1
				var kind: String=robot.brain.goal_kind
				row.kinds[kind]=row.kinds.get(kind,0)+1
				if robot.brain.stuck>0.5: row.blocked_frames += 1
			row.last=p
	var wall_ms_per_frame := float(Time.get_ticks_usec()-started_usec)/1000.0/total_frames
	var output := {"mode":mode,"count":count,"seconds":seconds,"seed":match_seed,"difficulty":game.difficulty,"difficulty_revision":BotDifficulty.data.revision,"wall_ms_per_frame":wall_ms_per_frame,"physics_ms_avg":average(physics_times),"physics_ms_peak":physics_times.max(),"process_ms_avg":average(frame_times),"flags":[{"state":game.flags[0].state,"carrier":game.flags[0].carrier},{"state":game.flags[1].state,"carrier":game.flags[1].carrier}],"robots":[]}
	output["match_elapsed"] = game.elapsed
	output["decision_phases"] = ArenaBrain.decision_phases
	output["phase"] = game.phase
	output["upper_floor_case"]=upper_floor_case
	output["team_scores"] = game.team_scores.duplicate()
	for id in count:
		var robot: ArenaRobot = game.robots[id]
		var row: Dictionary=stats[id]
		for key in ["last","lift","jumping","repairing","last_weapon","last_pickup","last_packs","reloading","last_shots"]: row.erase(key)
		row.kills=robot.kills
		row.deaths=robot.deaths
		row.captures=robot.captures
		row.shots=robot.network_shots
		row.armor=robot.ah
		row.carrying=robot.carrying
		row.end=robot.position
		if robot.brain:
			row.final_goal=robot.brain.goal_kind
			row.final_stuck=robot.brain.stuck
			if robot.brain.path_index < robot.brain.path.size(): row.final_step=robot.brain.path[robot.brain.path_index]
		output.robots.append(row)
	var result := JSON.stringify(output)
	print("BOT_PROFILE ",result)
	var prefix := "" if game.map_id == "skyfall" else game.map_id+"_"
	if game.difficulty != 1: prefix = "difficulty%d_" % game.difficulty + prefix
	if ArenaBrain.decision_phases != 1: prefix = "phases%d_" % ArenaBrain.decision_phases + prefix
	if not report_prefix.is_empty(): prefix = report_prefix + "_" + prefix
	var file := FileAccess.open(report_output if not report_output.is_empty() else "res://reports/bot_profile_%s%s_%d.json" % [prefix,mode.to_lower(),count],FileAccess.WRITE)
	if file: file.store_string(result)
	game.phase="Finished"
	for voice in game.audio.voices: voice.stop()
	OS.delay_msec(100)
	game.queue_free()
	for frame in 3: await physics_frame
	if exit_after: quit()

func average(values: Array[float]) -> float:
	if values.is_empty(): return 0.0
	var sum := 0.0
	for value in values: sum += value
	return sum/values.size()
