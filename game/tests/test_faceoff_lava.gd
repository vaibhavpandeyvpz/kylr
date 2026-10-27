extends GutTest

func interior(pit: Dictionary) -> Vector2:
	var polygon:=PackedVector2Array()
	for point in pit.rim:polygon.append(Vector2(point[0],point[1]))
	var triangles:=Geometry2D.triangulate_polygon(polygon)
	var best:=Vector2.ZERO;var largest:=0.0
	for index in range(0,triangles.size(),3):
		var a:=polygon[triangles[index]];var b:=polygon[triangles[index+1]];var c:=polygon[triangles[index+2]]
		var area:=absf((b-a).cross(c-a))
		if area>largest:largest=area;best=(a+b+c)/3.0
	return best

func make_game() -> ArenaMatch:
	var game:=ArenaMatch.new()
	game.map_id="faceoff";game.online=true;game.authority=false
	add_child_autofree(game)
	return game

func test_authored_pits_are_deep_and_navigation_has_no_bottom_waypoints():
	var game:=make_game()
	await wait_physics_frames(3)
	var definitions: Array=game.map.config.lava_pits
	assert_eq(definitions.size(),11)
	assert_not_null(game.map.lava)
	var space:=game.get_world_3d().direct_space_state
	for pit in definitions:
		assert_eq(float(pit.depth_m),10.0)
		var point:=interior(pit)
		var floor_hit:=space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(point.x,-2,point.y),Vector3(point.x,-12,point.y),1))
		assert_false(floor_hit.is_empty(),str(pit.name)+" retains a physical pit floor")
		if not floor_hit.is_empty():assert_almost_eq(float(floor_hit.position.y),-10.0,.06,str(pit.name)+" has a ten-metre excavation")
		assert_false(game.map.lava.contains_contact(Vector3(point.x,0,point.y)),"Passing above lava is safe")
		assert_eq(float(pit.surface_m),-.5)
		assert_true(game.map.lava.contains_contact(Vector3(point.x,-.51,point.y)),"Crossing molten surface is lethal")
	assert_false(game.map.lava.contains_contact(Vector3(0,-.51,0)),"Low altitude outside pits is not lava")
	var traversal:=TraversalGraph.new(game.map)
	traversal.build()
	assert_true(traversal.graph.native_routes,"Faceoff uses native walking segments with exact portal costs")
	assert_gt(traversal.graph.get_point_count(),0)
	for id in traversal.graph.get_point_ids():
		assert_false(game.map.lava.contains_contact(traversal.graph.get_point_position(id)),"No lava-floor navigation nodes")
	var crossings:={"jump":0,"charged_jump":0,"launch":0}
	for edge in traversal.actions:
		var kind: String=traversal.actions[edge]
		if not crossings.has(kind):continue
		var a:=traversal.graph.get_point_position(edge.x)
		var b: Vector3=traversal.destinations.get(edge,traversal.graph.get_point_position(edge.y))
		for pit in game.map.lava.pits:
			if LavaTraversal.crosses_polygon(a,b,pit.polygon):
				crossings[kind]+=1
				if kind=="charged_jump":assert_false(traversal.basic_graph.are_points_connected(edge.x,edge.y),"Charge-requiring shortcuts stay out of the normal graph")
				break
	print("LAVA_ROUTES ",JSON.stringify(crossings))
	for kind in crossings:assert_gt(int(crossings[kind]),0,"Feasible "+kind+" pit crossings are baked")

func test_lava_kills_protected_robot_on_contact_without_energy_drop():
	var game:=make_game()
	await wait_physics_frames(3)
	game.set_physics_process(false)
	game.authority=true
	var victim: ArenaRobot=game.add_robot(0,"Lava contact",0,true,"projector")
	victim.set_process(false);victim.set_physics_process(false)
	game.phase="Active"
	victim.protection=5.0;victim.spawn_remaining=0.0
	var point:=interior(game.map.config.lava_pits[0])
	victim.global_position=Vector3(point.x,-.55,point.y)
	victim.velocity=Vector3.DOWN
	victim._physics_process(1.0/60.0)
	assert_false(victim.alive,"Lava bypasses armor, shields and spawn protection")
	assert_eq(victim.deaths,1)
	assert_eq(game.corpses.size(),1)
	if not game.corpses.is_empty():assert_eq(float(game.corpses[0].ep),0.0,"No Energy Core remains in lava")

func test_bubbles_stay_in_their_pit_and_reduced_motion_stops_them():
	var game:=make_game()
	await wait_physics_frames(3)
	for seed_value in 6:
		game.elapsed=float(seed_value)*8.7
		game.map.lava._process(0.0)
		for pit in game.map.lava.pits:
			assert_true(Geometry2D.is_point_in_polygon(pit.point,pit.polygon))
	game.reduced_motion=true
	game.map.lava._process(0.0)
	for pit in game.map.lava.pits:
		assert_false(pit.bubble.visible)
		assert_false(pit.droplets.visible)

func test_volcanic_layers_cover_the_landscape_and_evening_sky_is_static():
	var config:=MapCatalog.find("faceoff")
	assert_eq(config.terrain_material,"volcanic_soil")
	var material:=PlanetaryTerrain.material("faceoff")
	for layer in PlanetaryTerrain.LAYERS:
		var texture:=material.get_shader_parameter(layer+"_albedo") as Texture2D
		assert_not_null(texture)
		assert_true(texture.resource_path.begins_with("res://assets/textures/volcanic_soil/"))
	assert_true(PlanetaryTerrain.material("faceoff",true).get_shader_parameter("local_surface"),"Native soil aprons retain anchored projection")
	var environment:=ArenaLighting.environment(false,config.environment)
	assert_true(environment.sky.sky_material is ProceduralSkyMaterial)
	assert_eq(environment.sky.process_mode,Sky.PROCESS_MODE_QUALITY,"Evening reflections do not rebake every frame")
