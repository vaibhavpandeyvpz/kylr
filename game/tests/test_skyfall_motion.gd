extends GutTest

func metadata() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(MapCatalog.find("skyfall").metadata))

func test_platform_groups_preserve_stacked_floors_and_quarter_metre_bounds():
	var groups: Dictionary={}
	for section in metadata().deck_sections:
		assert_eq(section.motion.kind,"bob")
		assert_eq(float(section.motion.bob_amplitude),.25)
		var period: float=section.motion.period
		var group: String=section.motion.group
		if groups.has(group):assert_eq(period,groups[group],"Stacked floors share one physical motion")
		groups[group]=period
		assert_almost_eq(MapCarriers.transform_at(0,section).origin,Vector3.ZERO,Vector3.ONE*.00001)
		assert_almost_eq(MapCarriers.transform_at(period*.25,section).origin.y,.25,.00001)
		assert_almost_eq(MapCarriers.transform_at(period*.75,section).origin.y,-.25,.00001)
	assert_eq(groups.size(),8)

func assembled() -> ArenaMatch:
	var game:=ArenaMatch.new()
	game.map_id="skyfall";game.online=true;game.authority=false
	add_child_autofree(game)
	while not game.initialization_complete:await wait_physics_frames(1)
	game.set_process(false);game.set_physics_process(false)
	game.map.start_map_assembly();game.map.assembly.seek(5,true);game.map.assembly.pause()
	game.map.start_loadout();game.phase="Loading";game.authority=true
	await wait_physics_frames(2)
	game.map.build_navigation()
	return game

func test_live_spawns_flags_and_native_solver_follow_their_platforms():
	var game: ArenaMatch=await assembled()
	var carriers: MapCarriers=game.map.carriers
	var graph: TraversalGraph.PortalTraversalAStar=game.map.nav
	var planner:=graph.native_planner
	assert_not_null(planner)
	var long_charged:=0
	for edge in game.map.traversal.actions:
		if game.map.traversal.actions[edge]!="charged_jump":continue
		var a: Vector3=graph.get_point_position(edge.x);var b: Vector3=graph.get_point_position(edge.y)
		if Vector2(a.x-b.x,a.z-b.z).length()>7.2:
			long_charged+=1
			assert_false(game.map.traversal.basic_graph.are_points_connected(edge.x,edge.y,false))
	assert_gt(long_charged,0,"Physical charged crossings extend beyond the old 7 m search radius")
	var source_points: Dictionary={}
	var markers: Dictionary={}
	var sections: Dictionary={}
	for marker in game.map.markers:markers[marker.name]=marker
	for section in carriers.sections:sections[section.name]=section
	assert_gt(carriers.contacts.size(),0)
	for contact in carriers.contacts:assert_true(sections.has(contact.deck),"Moving fixture points have a cached rigid carrier frame")
	for spawn in game.map.spawns:source_points[spawn.id]=spawn.point
	for time in [0.0,1.7,4.2,8.0]:
		game.elapsed=time;carriers.sample(time)
		await wait_physics_frames(1)
		assert_same(graph.native_planner,planner,"Bobbing updates the existing native planner")
		for spawn in game.map.spawns:
			var section: Dictionary=sections[markers[spawn.id].deck]
			assert_almost_eq(spawn.point,MapCarriers.transform_at(time,section)*source_points[spawn.id],Vector3.ONE*.0001)
		for team in 2:
			var marker: Dictionary=markers[game.map.config.flag_markers[team]]
			var expected: Vector3=MapCarriers.transform_at(time,sections[marker.deck])*MapCatalog.vector(marker.position_godot)
			assert_almost_eq(game.flags[team].home,expected,Vector3.ONE*.0001)
			assert_almost_eq(game.flags[team].node.global_position,expected,Vector3.ONE*.0001)
		for index in mini(20,carriers.moving_navigation.size()):
			var id: int=carriers.moving_navigation[index]
			assert_almost_eq(planner.walking.get_point_position(id),graph.get_point_position(id),Vector3.ONE*.00001)
			assert_almost_eq(graph.get_point_position(id),carriers.navigation_points[id].rest,Vector3.ONE*.00001,"Rest-frame graph points do not require physics-tick rewrites")
			var point: Vector3=game.map.traversal.position_of(id)
			var plain: Dictionary={"point":point,"from":point,"entry":point}
			var hinted: Dictionary=plain.duplicate(true);hinted["_point_node"]=id;hinted["_from_node"]=id
			carriers.bind_route([plain]);carriers.bind_route([hinted])
			assert_eq(hinted,plain,"Known route nodes bind exactly like a physical nearest-point query")
			assert_false(hinted.has("_point_node"));assert_false(hinted.has("_from_node"))
			var info: Dictionary=carriers.navigation_points[id]
			assert_almost_eq(game.map.traversal.position_of(id),MapCarriers.transform_at(time,sections[info.deck])*info.rest,Vector3.ONE*.00001)
	var terrain_materials:=0
	for mesh in game.map.find_children("*","MeshInstance3D",true,false):
		for index in mesh.mesh.get_surface_count():
			var material=mesh.get_active_material(index)
			if material is StandardMaterial3D and Assets.material_role(material.resource_name) in ["M_Regolith","M_RegolithLight","M_RegolithDark"]:
				terrain_materials+=1;assert_false(material.uv1_world_triplanar,"Regolith stays attached while platforms bob")
	assert_gt(terrain_materials,0)
	var flag: Dictionary=game.flags[0]
	flag.state="dropped";flag.falling=false
	flag.point=game.map.traversal.position_of(carriers.deck_navigation["A_island_1_lower"][0])
	flag.node.global_position=flag.point
	carriers.sample(game.elapsed)
	var dropped_local: Vector3=flag.dropped_carrier.local
	var dropped_section: Dictionary=sections[flag.dropped_carrier.deck]
	game.elapsed+=1.1;carriers.sample(game.elapsed)
	assert_almost_eq(flag.point,MapCarriers.transform_at(game.elapsed,dropped_section)*dropped_local,Vector3.ONE*.0001,"Dropped flags ride supported moving ground")

func test_stationary_robot_rides_a_complete_bob_cycle_without_falling():
	var game: ArenaMatch=await assembled()
	var carriers: MapCarriers=game.map.carriers
	var candidates: Array=carriers.deck_navigation["A_island_1_lower"]
	var point:=Vector3.INF
	for id in candidates:
		var candidate:=game.map.nav.get_point_position(id)
		if game.map.traversal.supported(candidate) and game.map.traversal.standing_clear(candidate) and not carriers.on_launch_pad(candidate):
			point=candidate;break
	assert_ne(point,Vector3.INF)
	if point==Vector3.INF:return
	var robot: ArenaRobot=game.add_robot(0,"Hover rider",0,true,"projector")
	robot.set_process(false);robot.set_physics_process(false)
	robot.spawn_remaining=0;robot.protection=0;robot.global_position=point+Vector3.UP*.03
	game.phase="Active"
	for frame in 421:
		game.elapsed=float(frame)/60
		carriers.sample(game.elapsed)
		robot.simulate_movement(1.0/60)
		await wait_physics_frames(1)
	assert_true(robot.alive,"A stationary rider remains on the moving physical deck")
	var section: Dictionary=carriers.sections.filter(func(value):return value.name=="A_island_1_lower")[0]
	assert_lt(absf(robot.position.y-(MapCarriers.transform_at(game.elapsed,section)*point).y),.15)
	assert_lt(Vector2(robot.position.x-point.x,robot.position.z-point.z).length(),.3)

func test_hunt_targets_live_decks_and_impossible_elevations_skip_path_searches():
	var game: ArenaMatch=await assembled()
	var id: int=game.map.carriers.deck_navigation["A_island_1_lower"][0]
	var point: Vector3=game.map.traversal.position_of(id)
	game.online=false
	var robot: ArenaRobot=game.add_robot(0,"Deck hunter",0,false,"projector")
	robot.set_process(false);robot.set_physics_process(false)
	robot.spawn_remaining=0;robot.protection=0;robot.global_position=point
	assert_true(robot.brain.plan_intent("objective"))
	assert_eq(robot.brain.goal_kind,"hunt")
	assert_gt(robot.brain.goal.y,30.0,"Hunting never targets the lethal ground below the arena")
	assert_false(robot.brain.path.is_empty())
	TraversalGraph.profile_paths=true;TraversalGraph.path_stats.clear()
	assert_eq(game.map.traversal.route(point,Vector3(6,0,22)),[])
	assert_eq(int(TraversalGraph.path_stats.get("calls",0)),0,"Reject impossible elevations before an AStar search")
	var traversal: TraversalGraph=game.map.traversal
	traversal.begin_planning_queries()
	assert_ne(robot.brain.equipment_travel(robot.brain.goal),INF)
	assert_false(robot.brain.navigation_route(robot.brain.goal,"weapon").is_empty())
	assert_eq(int(TraversalGraph.path_stats.get("equipment_route_hits",0)),1,"Commit reuses its synchronous resource-cost route")
	traversal.end_planning_queries()
	robot.brain.navigation_route(robot.brain.goal,"weapon")
	assert_eq(int(TraversalGraph.path_stats.get("equipment_route_hits",0)),1,"A later physics phase cannot reuse the resource route")
	traversal.begin_planning_queries()
	robot.brain.navigation_route(robot.brain.goal,"weapon")
	assert_eq(int(TraversalGraph.path_stats.get("equipment_route_hits",0)),1,"A fresh decision epoch rejects stale routes")
	traversal.end_planning_queries()
	TraversalGraph.profile_paths=false;TraversalGraph.path_stats.clear()

func test_welding_rides_the_carrier_and_geometry_checks_use_its_rest_frame():
	var game: ArenaMatch=await assembled()
	var station: Dictionary=game.map.fixtures.filter(func(f):return f.kind=="repair_station")[0]
	game.phase="Active"
	var patient: ArenaRobot=game.add_robot(0,"Moving bay patient",0,true,"projector")
	patient.set_process(false);patient.set_physics_process(false)
	patient.spawn_remaining=0;patient.protection=0;patient.ah=40;patient.velocity=Vector3.ZERO
	patient.global_position=station.point
	await wait_physics_frames(2)
	assert_true(game.map.start_repair(station,patient))
	game.map.tick_repair(station,1.01)
	assert_not_null(patient.repair)
	var mount: Node3D=Assets.socket(station.node,"PlayerMount")
	var offset: Vector3=patient.global_position-Assets.socket_world_transform(mount).origin
	patient.yaw+=.4
	var heading: float=patient.yaw
	for time in [1.7,3.1,5.0,7.3]:
		game.elapsed=time;game.map.carriers.sample(time)
		await wait_physics_frames(1)
		assert_true(game.map.repair_geometry_valid(station),"Carrier bobbing does not invalidate a native repair bay")
		assert_almost_eq(patient.global_position,Assets.socket_world_transform(mount).origin+offset,Vector3.ONE*.0001)
		assert_almost_eq(patient.yaw,heading,.0001,"Bobbing preserves the patient's look direction")
		patient.tick_repair_motion(.02)
		game.map.tick_repair(station,.01)
		assert_not_null(patient.repair)
	station.node.position.x+=.5
	assert_false(game.map.repair_geometry_valid(station),"Independent fixture displacement still invalidates geometry")
