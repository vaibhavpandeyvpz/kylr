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
			assert_between(float(pit.radius)*2.0,.05,.15,"Ambient bubbles peak at 5–15 cm diameter")
	game.reduced_motion=true
	game.map.lava._process(0.0)
	for pit in game.map.lava.pits:
		assert_false(pit.bubble.visible)
		assert_false(pit.droplets.visible)

func test_lava_death_sinks_over_standing_clip_and_holds_camera_above_the_bank():
	var game:=make_game()
	await wait_physics_frames(3)
	game.set_physics_process(false);game.set_process(false)
	game.phase="Active"
	var robot: ArenaRobot=game.add_robot(0,"Sinking",0,true,"projector")
	robot.set_physics_process(false);robot.set_process(false)
	game.local_robot=robot
	var point:=interior(game.map.config.lava_pits[0])
	robot.global_position=Vector3(point.x,-.6,point.y)
	robot.velocity=Vector3(12,-30,5)
	robot.crouched=true
	game.eliminate(robot,null,"Lava")
	var entry: Dictionary=game.corpses[0]
	var corpse: Node3D=entry.node
	var animator: AnimationPlayer=corpse.find_child("RuntimeAnimator",true,false)
	assert_eq(animator.current_animation,"common_death_front","Lava always uses the standing death")
	assert_false(entry.falling_out)
	assert_false(game.local_fall_death)
	assert_eq(entry.fall_velocity,0.0,"Fast incoming falls stop at the molten surface")
	assert_almost_eq(corpse.global_position.y,-.5,.001)
	var start:=corpse.global_position
	var bubbles:=corpse.get_node("LavaDeathBubbles") as LavaDeathBubbles
	assert_between(bubbles.bubbles.size(),20,25)
	assert_eq(bubbles.multimesh.instance_count,bubbles.bubbles.size()*4,"Bubbles and their spatters share one batch")
	var bubble_anchor:=bubbles.global_position
	var duration: float=animator.current_animation_length
	assert_almost_eq(robot.respawn_time,duration+1.0,.001)
	game._process(0)
	var camera_point: Vector3=game.camera_rig.cameras.death.global_position
	assert_gt(camera_point.y,1.0,"The cinematic stays above the ground")
	assert_true(game.combat.ray(start+Vector3.UP*.9,camera_point,[],1).is_empty(),"Clear upper silhouette")
	assert_true(game.combat.ray(start+Vector3.UP*.15,camera_point,[],1).is_empty(),"The bank does not hide the robot")
	game.tick_drops(duration*.5)
	animator.advance(duration*.5)
	assert_almost_eq(corpse.global_position,start-Vector3.UP*LavaDeath.SINK_DEPTH*.5,Vector3.ONE*.001,"Constant gentle sinking ignores gravity and knockback")
	game._process(0)
	assert_eq(game.camera_rig.cameras.death.global_position,camera_point,"Camera position never follows the sink")
	assert_eq(bubbles.global_position,bubble_anchor,"Bubbles remain on the lava surface as their parent sinks")
	assert_almost_eq(game.camera_rig.focus_anchors.death.global_position.y,corpse.global_position.y+.95,.001,"Only the look direction follows the body")
	game.tick_drops(duration*.5)
	animator.advance(duration*.5+.01)
	assert_almost_eq(corpse.global_position.y,start.y-LavaDeath.SINK_DEPTH,.001)
	var skeleton:=Assets.find(corpse,"Skeleton3D") as Skeleton3D
	for bone in skeleton.get_bone_count():
		assert_lt((skeleton.global_transform*skeleton.get_bone_global_pose(bone).origin).y,start.y-.2,"Every assembly has sunk under the opaque lava")
	var state:=RobotCorpse.snapshot(corpse)
	assert_eq(state.animation,"common_death_front","Late snapshots retain the finished death clip")
	var replica:=RobotCorpse.from_snapshot(game,robot,bytes_to_var(var_to_bytes(state)))
	assert_eq(replica.get_meta("lava_origin"),start,"Clients retain the surface anchor")
	assert_eq(replica.get_meta("lava_bubbles"),corpse.get_meta("lava_bubbles"),"Clients retain the random burst recipe")
	assert_eq(replica.global_transform,corpse.global_transform)
	assert_eq(RobotCorpse.snapshot(replica).animation,"common_death_front")
	replica.queue_free()
	game.tick_drops(.99)
	assert_eq(game.corpses.size(),1,"Keep the completed clip's one-second cleanup hold")
	game.tick_drops(.02)
	assert_true(game.corpses.is_empty())
	assert_true(game.drops.is_empty())

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

func test_online_lava_corpse_keeps_camera_fixed_across_snapshots_and_expires():
	var server:=make_game()
	await wait_physics_frames(3)
	server.set_physics_process(false);server.set_process(false)
	server.phase="Active"
	var robot: ArenaRobot=server.add_robot(0,"Remote sinking",0,true,"projector")
	robot.set_physics_process(false);robot.set_process(false)
	var point:=interior(server.map.config.lava_pits[1])
	robot.global_position=Vector3(point.x,-.55,point.y)
	server.eliminate(robot,null,"Lava")
	var sender:=OnlineTransport.new()
	sender.game=server;sender.closed=true;sender.peers[7]={"ack":0}
	add_child_autoqfree(sender)
	var client:=make_game()
	await wait_physics_frames(3)
	client.set_physics_process(false);client.set_process(false)
	var receiver:=OnlineTransport.new()
	receiver.game=client;receiver.closed=true;receiver.local_id=0
	add_child_autoqfree(receiver)
	receiver.apply_snapshot(bytes_to_var(var_to_bytes(sender.make_snapshot(7))),true)
	assert_eq(receiver.remote_corpses.size(),1)
	client._process(0)
	var replica:=client.local_death_corpse
	assert_true(replica.has_meta("lava_origin"))
	var burst:=replica.get_node("LavaDeathBubbles") as LavaDeathBubbles
	assert_eq(burst.bubbles,server.corpses[0].node.get_node("LavaDeathBubbles").bubbles,"Online burst positions, sizes and pop times agree")
	assert_false(client.local_fall_death)
	var camera_point: Vector3=client.camera_rig.cameras.death.global_position
	server.tick_drops(1.0)
	receiver.apply_snapshot(bytes_to_var(var_to_bytes(sender.make_snapshot(7))))
	client._process(0)
	assert_eq(client.camera_rig.cameras.death.global_position,camera_point)
	assert_same(replica.get_node("LavaDeathBubbles"),burst,"Repeated snapshots never replay or duplicate the burst")
	assert_eq(replica.global_transform,server.corpses[0].node.global_transform)
	server.tick_drops(10.0)
	receiver.apply_snapshot(sender.make_snapshot(7))
	assert_true(receiver.remote_corpses.is_empty())

func test_sinking_bubble_sizes_vary_and_stay_inside_every_pit():
	var game:=make_game()
	await wait_physics_frames(3)
	game.set_process(false);game.set_physics_process(false)
	var counts:={}
	for index in game.map.config.lava_pits.size():
		var pit: Dictionary=game.map.config.lava_pits[index]
		var point:=interior(pit)
		var corpse:=Node3D.new()
		game.add_child(corpse)
		corpse.global_position=Vector3(point.x,float(pit.surface_m),point.y)
		LavaDeath.begin(game,corpse,float(pit.surface_m),3.4,index*9176)
		var burst:=corpse.get_node("LavaDeathBubbles") as LavaDeathBubbles
		assert_between(burst.bubbles.size(),20,25)
		counts[burst.bubbles.size()]=true
		var polygon: PackedVector2Array=game.map.lava.pits[index].polygon
		var smallest:=INF;var largest:=0.0
		for bubble in burst.bubbles:
			assert_between(float(bubble.radius)*2.0,.05,.15,"Death bubbles peak at 5–15 cm diameter")
			assert_true(Geometry2D.is_point_in_polygon(bubble.point,polygon))
			assert_lte(bubble.radius,LavaDeathBubbles.edge_distance(bubble.point,polygon),"Entire bubbles and spatters clear the bank")
			assert_lte(bubble.point.distance_to(point),1.601,"The burst stays near the sinking robot")
			assert_lte(bubble.start+bubble.lifespan*1.2,3.401,"Pop before the death animation ends")
			smallest=minf(smallest,bubble.radius);largest=maxf(largest,bubble.radius)
		assert_gt(largest-smallest,.02,"Each burst has visibly different bubble sizes")
		game.reduced_motion=true
		burst._process(0)
		assert_false(burst.visible)
		game.reduced_motion=false
		game.elapsed=4.0;burst._process(0)
		assert_false(burst.visible,"Burst expires instead of looping")
		game.elapsed=0.0
		corpse.free()
	assert_gt(counts.size(),1,"Different entries choose different bubble counts")
