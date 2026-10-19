extends SceneTree

func _initialize(): run.call_deferred()

func run():
	var game := ArenaMatch.new()
	game.map_id = "faceoff"
	game.online = true
	root.add_child(game)
	await physics_frame
	await physics_frame
	game.map.start_map_assembly()
	game.map.assembly.seek(5,true)
	game.map.assembly.pause()
	game.map.start_loadout()
	for frame in 8: await physics_frame
	await create_timer(.5).timeout
	for spawn in game.map.spawns:
		Assets.play(spawn.node,spawn.action)
		var player:=Assets.find(spawn.node,"AnimationPlayer") as AnimationPlayer
		player.seek(spawn.duration,true);player.pause()
	await physics_frame
	game.map.build_navigation()
	await physics_frame
	var map: ArenaMap = game.map
	if "--boundary-only" in OS.get_cmdline_user_args():
		for direction in [Vector3.RIGHT,Vector3.LEFT,Vector3.FORWARD,Vector3.BACK]:
			for height in [1.0,20.0,80.0]:
				var hit=game.combat.ray(direction*36+Vector3.UP*height,direction*39+Vector3.UP*height,[],1)
				if not check(not hit.is_empty(),"Faceoff perimeter blocks ground and airborne exits"):return
				if not check(absf(hit.position.dot(direction)-37.5)<.002,"Faceoff boundary follows the 75 m canvas"):return
		print("FACEOFF_BOUNDARY 12 rays passed across four perimeter walls")
		game.free();await physics_frame;quit();return
	if not check(map.navigation_region.navigation_mesh.get_polygon_count()>0,"Faceoff collision must bake a navigation mesh"):return
	for spawn in map.spawns:
		for team in 2:
			if not check(not map.traversal.route(spawn.point,map.world_point(map.config.flag_bases[team]),false).is_empty(),"Every spawn must reach either flag without charged jumps"):return
	print("FACEOFF_NAV points=",map.nav.get_point_count()," polygons=",map.navigation_region.navigation_mesh.get_polygon_count())
	if "--nav-only" in OS.get_cmdline_user_args():
		game.free();await physics_frame;quit();return
	game.phase = "Active"
	game.online = false
	game.time_limit = 10000
	var robot := game.add_robot(0,"TraversalProbe",0,false,"projector") as ArenaRobot
	robot.protection = 0
	robot.spawn_remaining = 0
	robot.collision_layer = 2
	var cases := []
	for spawn in map.spawns:
		if spawn.action=="open":
			cases.append([spawn.mount.global_position,spawn.node.global_position+spawn.mount.global_basis.z*2,"spawn_world"])
	for ramp in map.config.walk_routes:
		cases.append([ramp[0],ramp[-1],"door_in"])
		cases.append([ramp[-1],ramp[0],"door_out"])
	for link in map.config.jump_links: cases.append([link.from,link.to,"pad"])
	for link in map.config.drop_links: cases.append([link.from,link.to,"drop"])
	for link in map.config.get("normal_jump_links",[]):
		cases.append([link.from,link.to,"jump_access"])
		for point in [map.world_point(link.from),map.world_point(link.to)]:
			var hit: Dictionary=game.combat.ray(point+Vector3.UP*.8,point-Vector3.UP*.45,[],1)
			print("JUMP_ENDPOINT ",point," clear=",map.traversal.standing_clear(point)," supported=",map.traversal.supported(point)," floor=",hit)
	for link in map.config.lift_links:
		cases.append([link.lower_exit,link.upper_exit,"lift_up"])
		cases.append([link.upper_exit,link.lower_exit,"lift_down"])
	for pair in map.config.portal_pairs:
		for direction in [pair,[pair[1],pair[0]]]:
			var entrance=map.fixture_by_id(direction[0]);var exit=map.fixture_by_id(direction[1])
			for side in [-1.0,1.0]:
				cases.append([entrance.point+entrance.node.global_basis.z*1.5*side,map.portal_exits(exit)[0],"portal_world"])
	cases.append([map.config.flag_bases[0],map.config.flag_bases[1],"cross_zone"])
	cases.append([map.config.flag_bases[1],map.config.flag_bases[0],"cross_zone"])
	var selected_case := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--only="):selected_case=argument.trim_prefix("--only=")
	selected_case={"spawn":"spawn_world","portal":"portal_world","speed_ramp":"speed_ramp_world"}.get(selected_case,selected_case)
	for item in cases:
		if not selected_case.is_empty() and item[2]!=selected_case:continue
		var start: Vector3 = item[0] if item[2].ends_with("_world") else map.world_point(item[0])
		var finish: Vector3 = item[1] if item[2].ends_with("_world") else map.world_point(item[1])
		robot.global_position = start+Vector3.UP*0.04
		robot.velocity = Vector3.ZERO
		robot.ramp_stage=0;robot.ramp_time=0
		robot.lift_target = -INF
		robot.portal_lock = 0
		robot.brain.reset()
		robot.brain.decision = 10000
		# Below the charged-jump threshold; zero EP intentionally kills a robot.
		robot.ep = 25
		robot.ah = 100
		var chamber: Dictionary={}
		if item[2]=="spawn_world":
			for spawn in map.spawns:
				if spawn.mount.global_position.distance_to(start)<.1:
					chamber=map.fixture_by_id(spawn.id)
					robot.spawn_fixture=spawn;robot.spawn_started=true;robot.spawn_remaining=spawn.duration+.1
					robot.move_input=Vector2.ZERO
					map.begin_spawn(spawn,robot)
					await create_timer(spawn.duration+.15).timeout
					robot.protection=0
		if not robot.brain.commit_goal(finish,"patrol"):
			print("MISSING_ANCHORS ",start," ",map.nav.get_point_position(map.nav.get_closest_point(start))," ",finish," ",map.nav.get_point_position(map.nav.get_closest_point(finish))," links=",map.traversal.entries)
			check(false,"Missing physical route for "+str(item));return
		var arrived := false
		var ramp_activated := false
		for frame in 3600:
			await physics_frame
			robot.ep=25
			if robot.ramp_stage!=0:ramp_activated=true
			if frame%120==0 and "--trace" in OS.get_cmdline_user_args():
				print("PHYSICAL_TRACE ",frame/60," pos=",robot.position," velocity=",robot.velocity," floor=",robot.is_on_floor()," lift=",robot.lift_target," goal=",robot.brain.goal," step=",robot.brain.path[robot.brain.path_index] if robot.brain.path_index<robot.brain.path.size() else {})

			if frame%120==0 and "--contacts" in OS.get_cmdline_user_args():
				var delta: Vector3=finish-robot.position;delta.y=0
				var contact:=KinematicCollision3D.new()
				var blocked:=robot.test_move(robot.global_transform,delta.normalized()*.2,contact)
				print("CONTACT ",robot.position," blocked=",blocked," collider=",contact.get_collider() if blocked else null," normal=",contact.get_normal() if blocked else Vector3.ZERO," position=",contact.get_position() if blocked else Vector3.ZERO)

			var tolerance:=0.35 if String(item[2]).begins_with("lift_") else 1.0
			if robot.global_position.distance_to(finish)<tolerance and absf(robot.global_position.y-finish.y)<0.1 and robot.is_on_floor(): arrived=true; break
		print("FACEOFF_PHYSICAL ",item[2]," arrived=",arrived," end=",robot.global_position," target=",finish)
		if item[2]=="speed_ramp_world" and not ramp_activated:arrived=false
		if arrived and not chamber.is_empty():
			await create_timer(1.0).timeout
			if not check(not chamber.open and not chamber.close_pending,"Stasis closes once after native spawn egress"):return
			print("STASIS_EGRESS closed=true id=",chamber.id)
		if not arrived:
			game.free()
			quit(1)
			return
	for voice in game.audio.voices: voice.stop()
	# Fixed-FPS probes can advance timers faster than the real audio mixer.
	# Wait in wall-clock time, as App.request_quit() does, before teardown.
	var deadline := Time.get_ticks_msec()+100
	while Time.get_ticks_msec()<deadline: await process_frame
	game.free()
	deadline=Time.get_ticks_msec()+100
	while Time.get_ticks_msec()<deadline: await process_frame
	quit()

func check(condition: bool,message: String) -> bool:
	if not condition:
		push_error(message)
		quit(1)
	return condition
