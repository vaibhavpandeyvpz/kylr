extends GutTest

func test_shared_planetary_material_retains_all_packed_layers():
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/textures/planetary/manifest.json"))
	for map_id: String in manifest.maps:
		var material := PlanetaryTerrain.material(map_id)
		assert_eq(material,PlanetaryTerrain.material(map_id),"Terrain chunks share one material per map")
		for index in 2:
			var control: Texture2D=material.get_shader_parameter("weights"+str(index))
			assert_not_null(control)
			if control:assert_eq(control.get_size(),Vector2(512,512))
		for layer: String in manifest.layers:
			for channel in ["_albedo","_normal"]:
				var texture: Texture2D=material.get_shader_parameter(layer+channel)
				assert_not_null(texture)
				if texture:assert_eq(texture.get_size(),Vector2(2048,2048))

func test_baked_terrain_collision_matches_source_landforms_and_lethality():
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/textures/planetary/manifest.json"))
	for map_id: String in manifest.maps:
		var game := ArenaMatch.new()
		game.online=true;game.map_id=map_id
		add_child(game)
		await wait_physics_frames(3)
		game.set_physics_process(false);game.set_process(false)
		var terrain_surfaces:=0
		for mesh in game.map.find_children("*","MeshInstance3D",true,false):
			for surface in mesh.mesh.get_surface_count():
				var material=mesh.get_active_material(surface)
				if material is ShaderMaterial and material.shader==PlanetaryTerrain.SHADER:
					terrain_surfaces+=1
		assert_gt(terrain_surfaces,0,map_id+" imported terrain receives the packed PBR material")
		assert_lt(float(game.map.config.fall_boundary),float(manifest.maps[map_id].min_height_m)-2.0,"Void boundary stays beneath the deepest terrain")
		for values: Array in manifest.maps[map_id].qa_points:
			var expected := Vector3(values[0],values[1],values[2])
			var query := PhysicsRayQueryParameters3D.create(expected+Vector3.UP*.4,expected-Vector3.UP*.4,1)
			var contact := game.get_world_3d().direct_space_state.intersect_ray(query)
			assert_false(contact.is_empty(),map_id+" terrain has physical support at source sample")
			if not contact.is_empty():
				assert_almost_eq(float(contact.position.y),expected.y,.005,"Collision follows baked landform height")
				assert_eq(bool(contact.collider.get_meta("lethal_surface",false)),map_id=="skyfall")
		game.queue_free();await wait_physics_frames(2)

func test_deployed_lander_has_ground_under_its_complete_footprint():
	var game:=ArenaMatch.new()
	game.online=true;game.map_id="faceoff"
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_physics_process(false);game.set_process(false)
	var marker: Dictionary={}
	for item: Dictionary in game.map.markers:
		if item.asset=="lunar_lander":marker=item;break
	assert_false(marker.is_empty())
	if marker.is_empty():return
	var fixture=game.map.fixture_by_id(marker.name)
	var excluded: Array[RID]=[]
	for body in fixture.node.find_children("*","CollisionObject3D",true,false):excluded.append(body.get_rid())
	var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/environments/lunar_lander/lunar_lander_rig.json"))
	var bounds: Dictionary=metadata.bounds_m
	var yaw: float=marker.rotation_blender[2]
	var center:=MapCatalog.vector(marker.position_godot)
	for lx: float in [bounds.lo[0],0.0,bounds.hi[0]]:
		for ly: float in [bounds.lo[1],0.0,bounds.hi[1]]:
			var local_point:=center+Vector3(cos(yaw)*lx-sin(yaw)*ly,0,-sin(yaw)*lx-cos(yaw)*ly)
			var point:=game.map.world_point([local_point.x,local_point.y,local_point.z])
			var query:=PhysicsRayQueryParameters3D.create(point+Vector3.UP*.2,point-Vector3.UP*.2,1)
			query.exclude=excluded
			var hit:=game.get_world_3d().direct_space_state.intersect_ray(query)
			assert_false(hit.is_empty(),"Terrain supports the deployed lander footprint")
			if not hit.is_empty():assert_almost_eq(float(hit.position.y),point.y,.005,"Ground meets native foot and ladder plane")

func test_bots_can_walk_from_the_cover_bank_to_level_ground():
	var game := ArenaMatch.new()
	game.online=true;game.map_id="faceoff"
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_physics_process(false);game.set_process(false)
	game.map.start_map_assembly();game.map.assembly.seek(5.0,true)
	await wait_physics_frames(2)
	game.map.build_navigation()
	await wait_physics_frames(2)
	var graph: AStar3D=game.map.nav
	var manifest: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/textures/planetary/manifest.json"))
	var sample: Array=manifest.maps.faceoff.qa_points[1]
	var summit:=Vector3(sample[0],sample[1],sample[2])
	var first:=graph.get_closest_point(summit)
	assert_lt(graph.get_point_position(first).distance_to(summit),1.5,"Cover bank has sampled bot support")
	var pending: Array[int]=[first]
	var visited: Dictionary={first:true}
	var reaches_level_ground:=false
	while not pending.is_empty():
		var current: int=pending.pop_back()
		if absf(graph.get_point_position(current).y)<.2:reaches_level_ground=true;break
		for next in graph.get_point_connections(current):
			if visited.has(next) or game.map.traversal.actions.has(Vector2i(current,next)):continue
			visited[next]=true;pending.append(next)
	assert_true(reaches_level_ground,"Continuous walking routes connect the summit to the outpost")
	for point: Vector3 in game.map.navigation_region.navigation_mesh.get_vertices():
		assert_lte(absf(point.x),37.5,"Distant terrain is not navigable")
		assert_lte(absf(point.z),37.5,"Distant terrain is not navigable")
