extends GutTest

func test_reused_navigation_capsules_keep_fresh_native_contacts():
	var game := make_match()
	await prepare_map(game)
	var body := StaticBody3D.new()
	add_child_autofree(body)
	var collision := CollisionShape3D.new()
	var obstacle := BoxShape3D.new()
	obstacle.size = Vector3(0.2,0.2,2)
	collision.shape = obstacle
	body.add_child(collision)
	var nav: TraversalGraph = game.map.traversal
	var start := Vector3(100,10,100)
	var finish := Vector3(102,10,100)
	for height in [0.0,0.2,2.0,0.0]:
		collision.disabled = height == 0.0
		obstacle.size.y = maxf(height,0.2)
		body.position = Vector3(101,10+height/2,100)
		await wait_physics_frames(2)
		nav.reuse_query_shapes = false
		var forward := nav.movement_clear(start,finish)
		var reverse := nav.movement_clear(finish,start)
		var standing := nav.standing_clear(Vector3(101,10,100))
		nav.reuse_query_shapes = true
		assert_eq(nav.movement_clear(start,finish),forward,"Shared shape preserves forward sweep and step checks")
		assert_eq(nav.movement_clear(finish,start),reverse,"Query transforms remain independent")
		assert_eq(nav.standing_clear(Vector3(101,10,100)),standing,"Later queries see changed native geometry")
	assert_not_null(nav.movement_capsule)
	assert_not_null(nav.standing_capsule)
	assert_almost_eq(nav.movement_capsule.height,1.75,0.000001)
	assert_almost_eq(nav.standing_capsule.height,1.72,0.000001)
	assert_ne(nav.movement_capsule.get_rid(),nav.standing_capsule.get_rid(),"Different dimensions retain separate shapes")
	assert_true(nav.movement_clear(start,finish),"Removing the obstacle restores the route")

func test_planning_sweeps_reuse_results_only_before_world_changes():
	var game := make_match()
	await prepare_map(game)
	var body := StaticBody3D.new()
	add_child_autofree(body)
	var collision := CollisionShape3D.new()
	var wall := BoxShape3D.new()
	wall.size = Vector3(0.2,2,2)
	collision.shape = wall
	collision.disabled = true
	body.add_child(collision)
	body.position = Vector3(101,11,100)
	await wait_physics_frames(2)
	var start := Vector3(100,10,100)
	var finish := Vector3(102,10,100)
	var previous_profiling := ArenaCombat.profile_queries
	var previous_stats := ArenaCombat.query_stats.duplicate()
	ArenaCombat.profile_queries = true
	ArenaCombat.query_stats.clear()
	game.map.traversal.begin_planning_queries()
	assert_true(game.map.traversal.movement_clear(start,finish))
	var first_calls := int(ArenaCombat.query_stats.get("ray_calls",0))
	assert_gt(first_calls,0,"First sweep queries the native world")
	assert_true(game.map.traversal.movement_clear(start,finish))
	assert_eq(int(ArenaCombat.query_stats.get("ray_calls",0)),first_calls,"Identical scoped sweep uses no new rays")
	game.map.traversal.end_planning_queries()
	game.map.traversal.planning_cache_enabled = false
	game.map.traversal.begin_planning_queries()
	assert_true(game.map.traversal.movement_clear(start,finish))
	var unscoped_calls := int(ArenaCombat.query_stats.get("ray_calls",0))
	assert_true(game.map.traversal.movement_clear(start,finish))
	assert_gt(int(ArenaCombat.query_stats.get("ray_calls",0)),unscoped_calls,"Disabled cache runs fresh native queries")
	game.map.traversal.end_planning_queries()
	game.map.traversal.planning_cache_enabled = true
	collision.disabled = false
	await wait_physics_frames(2)
	game.map.traversal.begin_planning_queries()
	assert_false(game.map.traversal.movement_clear(start,finish),"A later planning update sees the new wall")
	game.map.traversal.end_planning_queries()
	assert_false(game.map.traversal.movement_clear(start,finish),"Unscoped motor queries remain live")
	ArenaCombat.profile_queries = previous_profiling
	ArenaCombat.query_stats = previous_stats

func test_combined_motor_probe_preserves_steps_walls_and_headroom():
	var game := make_match()
	await prepare_map(game)
	var robot := game.add_robot(0,"Motor Probe",0,false,"projector") as ArenaRobot
	robot.set_physics_process(false)
	robot.set_process(false)
	robot.position = Vector3(100,10,100)
	var floor_body := StaticBody3D.new()
	add_child_autofree(floor_body)
	var floor_collision := CollisionShape3D.new()
	var floor_shape := BoxShape3D.new()
	floor_shape.size = Vector3(4,0.2,4)
	floor_collision.shape = floor_shape
	floor_body.add_child(floor_collision)
	floor_body.position = Vector3(100,9.9,100)
	var body := StaticBody3D.new()
	add_child_autofree(body)
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(0.2,0.2,1.2)
	collision.shape = shape
	body.add_child(collision)
	body.position = Vector3(100.6,10.1,100)
	var travel := Vector3(0.6,0,0)
	await wait_physics_frames(2)
	assert_true(robot.walk_or_step_motion_clear(travel),"Native capsule clears a supported low step")
	assert_eq(robot.walk_or_step_motion_clear(travel),robot.walk_motion_clear(travel) or robot.can_step_up(travel))
	shape.size.y = 2.0
	body.position.y = 11.0
	await wait_physics_frames(2)
	assert_false(robot.walk_or_step_motion_clear(travel),"A tall wall still blocks the motor")
	shape.size.y = 0.2
	body.position.y = 10.1
	var ceiling := StaticBody3D.new()
	add_child_autofree(ceiling)
	var roof := CollisionShape3D.new()
	var roof_shape := BoxShape3D.new()
	roof_shape.size = Vector3(4,0.2,4)
	roof.shape = roof_shape
	ceiling.add_child(roof)
	ceiling.position = Vector3(100,11.84,100)
	await wait_physics_frames(2)
	assert_false(robot.walk_or_step_motion_clear(travel),"Step keeps native head clearance")
	assert_eq(robot.walk_or_step_motion_clear(travel),robot.walk_motion_clear(travel) or robot.can_step_up(travel))
	collision.disabled = true
	roof.disabled = true
	await wait_physics_frames(2)
	assert_true(robot.walk_or_step_motion_clear(travel),"Open floor retains ordinary walking")
	assert_true(robot.walk_or_step_motion_clear(Vector3.ZERO),"Stationary motor remains clear")

func test_ctf_public_interception_projects_void_search_onto_reachable_floor():
	var game := make_match()
	game.match_type = "CTF"
	await prepare_map(game)
	game.phase = "Active"
	for team in 2:
		var actor: ArenaRobot = game.add_robot(team,"Carrier",team,false,"projector")
		actor.set_physics_process(false)
		actor.brain = ArenaBrain.new(actor)
		actor.position = game.flags[1-team].home
		var raw: Vector3 = game.flags[1-team].home.lerp(game.flags[team].home,.35)
		var search: Vector3 = actor.brain.interception_point(-1)
		assert_gt(search.distance_to(raw),2.0,"Raw interpolation is over Skyfall's void")
		assert_true(actor.brain.commit_goal(search,"intercept"),"Public search remains a reachable emergency goal")
		assert_true(game.map.traversal.supported(search))
		assert_lt(actor.brain.path.back().point.distance_to(search),.1)

func test_walk_clearance_steps_over_low_stones_but_preserves_walls_and_headroom():
	var game:=make_match()
	await prepare_map(game)
	var body:=StaticBody3D.new();add_child_autofree(body)
	var collision:=CollisionShape3D.new();var shape:=BoxShape3D.new()
	shape.size=Vector3(.2,.2,1.2);collision.shape=shape;body.add_child(collision)
	body.position=Vector3(100,10.1,100)
	await wait_physics_frames(2)
	var a:=Vector3(99,10,100);var b:=Vector3(101,10,100)
	assert_true(game.map.traversal.movement_clear(a,b),"Walkable gravel does not become a jump gap")
	shape.size.y=.6;body.position.y=10.3
	await wait_physics_frames(2)
	assert_false(game.map.traversal.movement_clear(a,b),"A taller obstruction still blocks walking")
	shape.size.y=.2;body.position.y=10.1
	var ceiling:=StaticBody3D.new();add_child_autofree(ceiling)
	var roof:=CollisionShape3D.new();var roof_shape:=BoxShape3D.new()
	roof_shape.size=Vector3(2,.2,2);roof.shape=roof_shape;ceiling.add_child(roof)
	ceiling.position=Vector3(100,11.9,100)
	await wait_physics_frames(2)
	assert_false(game.map.traversal.movement_clear(a,b),"Stepping must retain clearance for the robot's head")

func test_speed_ramp_links_use_native_triggers_and_safe_ballistic_arcs():
	var game:=ArenaMatch.new();game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause()
	game.map.start_loadout();await wait_physics_frames(5)
	game.map.build_navigation()
	var minimum_y:=INF
	for vertex in game.map.navigation_region.navigation_mesh.vertices:minimum_y=minf(minimum_y,vertex.y)
	assert_gt(minimum_y,10.0,"Lethal lunar terrain is absent from the baked navmesh")
	var count:=0
	for ramp in game.map.config.speed_ramp_links:
		var fixture=game.map.fixture_by_id(ramp.fixture)
		assert_not_null(fixture.trigger)
		assert_not_null(fixture.launch_mount)
		var forward:=game.map.speed_ramp_velocity(fixture,float(ramp.speed));forward.y=0;forward=forward.normalized()
		var route:=game.map.traversal.route(fixture.point-forward*1.1,game.map.world_point(ramp.to),false)
		assert_true(route.any(func(step):return step.action=="speed_ramp"),"Low-EP route uses the ramp edge")
		assert_true(route[-1].point.distance_to(game.map.world_point(ramp.to))<.8)
		count+=1
	assert_eq(count,2)

func make_match(multiplier := 0.0) -> ArenaMatch:
	var game := ArenaMatch.new()
	game.online = true
	game.gravity_multiplier_override = multiplier
	add_child_autofree(game)
	return game

func prepare_map(game: ArenaMatch) -> void:
	await wait_physics_frames(3)
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0, true)
	game.map.start_loadout()
	await wait_physics_frames(2)
	game.map.build_navigation()

func test_both_roofs_reach_opposing_zone_and_portals_have_real_entries():
	var game := make_match()
	await prepare_map(game)
	for spawn in game.map.spawns:
		if spawn.point.y < 5: continue
		var opposing: Vector3=game.flags[1-spawn.team].home
		var route: Array=game.map.traversal.route(spawn.point,opposing)
		assert_false(route.is_empty(),"Spawn "+spawn.id+" has a traversable route to the opposing zone")
		if not route.is_empty(): assert_lt(route[-1].point.distance_to(opposing),2.0)
	for pair in game.map.config.portal_pairs:
		var entrance: Dictionary=game.map.fixture_by_id(pair[0])
		var exit: Dictionary=game.map.fixture_by_id(pair[1])
		var route: Array=game.map.traversal.route(entrance.point+entrance.node.global_basis.z*1.5,game.map.portal_exits(exit)[0])
		var portals: Array=route.filter(func(step): return step.action=="portal")
		assert_gt(portals.size(),0,str(pair)+" uses an explicit portal action")
		if not portals.is_empty(): assert_almost_eq(portals[0].entry,entrance.point,Vector3.ONE*0.01)

func test_gravity_override_propagates_to_match_effects_and_navigation():
	var game := make_match(1.5)
	await prepare_map(game)
	assert_eq(game.gravity_multiplier, 1.5)
	assert_almost_eq(game.gravity, ArenaTuning.GRAVITY * 1.5, 0.001)
	assert_almost_eq(game.effects.gravity, game.gravity, 0.001)
	assert_not_null(game.map.traversal)

func test_charged_edges_are_excluded_without_energy():
	var game := make_match()
	await prepare_map(game)
	var charged := 0
	for action in game.map.traversal.actions:
		if game.map.traversal.actions[action]!="charged_jump": continue
		charged+=1
		var from: Vector3=game.map.traversal.graph.get_point_position(action.x)
		var to: Vector3=game.map.traversal.graph.get_point_position(action.y)
		assert_false(game.map.traversal.basic_graph.are_points_connected(action.x,action.y),"Low-EP graph must exclude charged edge")
		assert_true(game.map.traversal.arc_clear(from,to,ArenaTuning.CHARGED_JUMP_HEIGHT),"Charged edge must match the live charged-jump cutoff")
	assert_gt(charged,0,"Map exposes tested charged-jump routes")

func test_barricade_closure_updates_navigation_and_reopening_restores_it():
	var game := make_match()
	await prepare_map(game)
	var barricade: Dictionary
	for fixture in game.map.fixtures:
		if fixture.kind == "barricade":
			barricade = fixture
			break
	assert_false(barricade.is_empty())
	var local_points: Array[int] = []
	for id in game.map.traversal.graph.get_point_ids():
		var local: Vector3 = barricade.node.to_local(game.map.traversal.graph.get_point_position(id))
		if absf(local.x) < 2.3 and absf(local.z) < 1.25 and absf(local.y) < 1.5: local_points.append(id)
	assert_gt(local_points.size(),0)
	for nav in [game.map.traversal.graph,game.map.traversal.basic_graph]:
		nav.cached_path(local_points[0],local_points[0])
		assert_false(nav.path_cache.is_empty())
	game.map.set_barricade(barricade,false)
	for nav in [game.map.traversal.graph,game.map.traversal.basic_graph]:
		assert_true(nav.path_cache.is_empty(),"Closing a barrier invalidates cached routes")
	for id in local_points:
		assert_true(game.map.traversal.graph.is_point_disabled(id))
		assert_true(game.map.traversal.basic_graph.is_point_disabled(id))
	var detour: Array = game.map.traversal.route(barricade.point + Vector3(0, 0, -4), barricade.point + Vector3(0, 0, 4))
	assert_gt(detour.size(), 0)
	for step in detour:
		var local: Vector3 = barricade.node.to_local(step.point)
		assert_false(absf(local.x) < 2.3 and absf(local.z) < 1.25 and absf(local.y) < 1.5)
	game.map.set_barricade(barricade,true)
	assert_true(game.map.traversal.graph.path_cache.is_empty(),"Opening also invalidates cached failures and detours")
	for id in local_points:
		assert_false(game.map.traversal.graph.is_point_disabled(id))

func test_every_skyfall_pad_route_physically_launches_and_lands():
	var game := make_match()
	await prepare_map(game)
	game.phase = "Active"
	game.goal = 1000
	game.time_limit = 10000
	var robot := game.add_robot(0,"Pad Route Probe",0,false,"projector") as ArenaRobot
	robot.brain = ArenaBrain.new(robot)
	var nav: TraversalGraph = game.map.traversal
	for jump in game.map.config.jump_links:
		var entry: Vector3 = game.map.world_point(jump.from)
		var destination: Vector3 = game.map.world_point(jump.to)
		var source: Vector3 = nav.graph.get_point_position(nav.graph.get_closest_point(entry))
		robot.brain.reset()
		robot.position = source + Vector3.UP * 0.02
		robot.velocity = Vector3.ZERO
		robot.lift_target = -INF
		robot.lift_from_pad = false
		robot.ep = 100
		robot.protection = 0
		robot.spawn_remaining = 0
		robot.brain.decision = 999
		robot.brain.retarget = 999
		robot.brain.goal = destination
		robot.brain.goal_kind = "probe"
		robot.brain.path = nav.route(source,destination,false)
		var launched := false
		var landed := false
		for frame in 420:
			await wait_physics_frames(1)
			if robot.lift_from_pad: launched = true
			if launched and robot.is_on_floor() and robot.position.distance_to(destination) < 2:
				landed = true
				break
		assert_true(launched,"Pad %s activates through normal movement" % entry)
		assert_true(landed,"Pad %s reaches its supported landing" % entry)
	game.phase = "Finished"

func test_jump_pad_launch_supersedes_a_short_jump_into_its_trigger():
	var game := make_match()
	await prepare_map(game)
	game.phase = "Active"
	var pad: Dictionary
	for fixture in game.map.fixtures:
		if fixture.kind == "jump_pad" and fixture.point.z > 0:
			pad = fixture
			break
	assert_false(pad.is_empty())
	var robot := game.add_robot(0,"Launch Probe",0,false,"projector") as ArenaRobot
	robot.protection = 0.0
	robot.position = pad.point + Vector3(0.04,0,0.08)
	robot.brain = ArenaBrain.new(robot)
	var brain: ArenaBrain = robot.brain
	brain.goal_kind = "repair"
	brain.goal = game.flags[0].home
	brain.path = [{"point":pad.point,"action":"jump","from":pad.point + Vector3(0,0,1),"entry":Vector3.INF}]
	brain.path_index = 0
	brain.transition_index = 0
	brain.transition_launched = true
	robot.begin_powered_jump(15.0, ArenaTuning.JUMP_PAD_SPEED, true)
	brain.steer(1.0 / 60.0)
	assert_eq(brain.transition_index,-1,"Powered lift completes the stale jump transition")
	assert_false(brain.path.is_empty(),"The bot replans from its physical pad position")

func test_barricade_change_preserves_committed_airborne_route():
	var game := make_match()
	await prepare_map(game)
	var robot := game.add_robot(0,"Airborne Probe",0,false,"projector") as ArenaRobot
	robot.position = Vector3(0,12,0)
	robot.brain = ArenaBrain.new(robot)
	robot.brain.path = [{"point":Vector3(0,7.25,10),"action":"drop","from":robot.position,"entry":Vector3.INF}]
	robot.brain.transition_index = 0
	robot.brain.transition_launched = true
	var barricade: Dictionary
	for fixture in game.map.fixtures:
		if fixture.kind == "barricade":
			barricade = fixture
			break
	game.map.set_barricade(barricade,false)
	assert_eq(robot.brain.transition_index,0,"A plate must not redirect an airborne bot to another floor")
	assert_eq(robot.brain.path.size(),1)
	assert_eq(robot.brain.path[0].action,"drop")
