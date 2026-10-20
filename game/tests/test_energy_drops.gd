extends GutTest

func make_drop_world() -> ArenaMatch:
	var game := ArenaMatch.new()
	game.online=true
	game.map_id="faceoff"
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_physics_process(false)
	game.authority=false
	game.phase="Active"
	var floor_body := StaticBody3D.new()
	var floor_shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size=Vector3(8,1,8)
	floor_shape.shape=box
	floor_body.add_child(floor_shape)
	game.add_child(floor_body)
	floor_body.global_position=Vector3(200,99.5,0)
	for id in 2:
		var robot: ArenaRobot = game.add_robot(id,"Killer" if id==0 else "Bot",id,id==0,"projector")
		robot.set_physics_process(false)
		robot.set_process(false)
		robot.protection=0
		robot.spawn_remaining=0
		robot.sh=0
		robot.global_position=Vector3(230 if id==0 else 200,100,0)
		robot.last_safe=robot.global_position
	await wait_physics_frames(2)
	return game

func kill_and_wait_for_drop(game: ArenaMatch) -> void:
	var victim: ArenaRobot=game.robots[1]
	victim.ep=63.5
	assert_true(victim.hit(1000,game.robots[0],"pistol"))
	assert_false(victim.alive)
	assert_eq(game.corpses.size(),1)
	game.tick_drops(float(game.corpses[0].time)-0.001)
	assert_eq(game.drops.size(),0,"Drop waits for the corpse's final-pose hold")
	game.tick_drops(0.002)
	assert_eq(game.drops.size(),7,"Remaining energy splits into 10 EP cores and a remainder")

func test_bot_armor_death_drops_the_remaining_energy_on_the_floor():
	var game := await make_drop_world()
	kill_and_wait_for_drop(game)
	if game.drops.is_empty():return
	var drop: Dictionary=game.drops[0]
	assert_eq(drop.ep,10.0)
	assert_eq(game.drops[-1].ep,3.5)
	var total := 0.0
	for core in game.drops: total += core.ep
	assert_eq(total,63.5)
	assert_almost_eq(drop.node.global_position.y,100.2,0.002)
	assert_true(drop.node.is_visible_in_tree())
	assert_not_null(drop.node.visual.find_child("SK_CoreSphereShell",true,false))
	assert_not_null(drop.node.visual.find_child("SK_CoreBoltShroud",true,false))
	game.tick_drops(29.99)
	assert_eq(game.drops.size(),7,"Lifetime starts at appearance, not death")
	game.tick_drops(0.02)
	assert_eq(game.drops.size(),0)

func test_drop_homing_and_collection_use_world_positions():
	var game := await make_drop_world()
	game.effects.position=Vector3(12,0,0)
	game.effects.rotation.y=0.6
	game.effects.scale=Vector3(2,1,2)
	kill_and_wait_for_drop(game)
	if game.drops.is_empty():return
	var killer: ArenaRobot=game.robots[0]
	killer.ep=10
	killer.global_position=Vector3(205,100,0)
	var start: Vector3=game.drops[0].node.global_position
	game.tick_drops(0.1)
	assert_eq(game.drops[0].claim,killer.robot_id,"Nearby killer claims the drop despite its parent's transform")
	assert_almost_eq(start.distance_to(game.drops[0].node.global_position),0.1,0.0001,"Core travels at 1 m/s")
	assert_almost_eq(game.drops[0].node.global_position,start.move_toward(killer.body_shape.global_position,0.1),Vector3.ONE*0.0001,"Core homes toward the body's centre")
	assert_eq(killer.ep,10.0,"Energy transfers only on arrival")
	killer.body_shape.position.y=0.59
	var previous: Vector3=game.drops[0].node.global_position
	game.tick_drops(0.1)
	assert_almost_eq(game.drops[0].node.global_position,previous.move_toward(killer.body_shape.global_position,0.1),Vector3.ONE*0.0001,"Homing follows the crouched body centre")
	for step in 90:game.tick_drops(0.1)
	assert_eq(game.drops.size(),0)
	assert_eq(killer.ep,73.5,"Stored energy is added once")
	game.tick_drops(0.1)
	assert_eq(killer.ep,73.5)

func test_bot_killer_receives_the_dropped_energy():
	var game := await make_drop_world()
	var killer: ArenaRobot=game.robots[0]
	killer.human=false
	# Bot damage scaling must still reach the same armor-death/drop path.
	kill_and_wait_for_drop(game)
	killer.ep=10
	killer.global_position=Vector3(205,100,0)
	for step in 90:game.tick_drops(0.1)
	assert_eq(game.drops.size(),0)
	assert_eq(killer.ep,73.5)

func test_uncredited_armor_death_leaves_a_contact_collectible_core():
	var game := await make_drop_world()
	var victim: ArenaRobot=game.robots[1]
	victim.ep=42.0
	assert_true(victim.hit(1000,null,"pistol"))
	game.tick_drops(float(game.corpses[0].time)+0.001)
	assert_eq(game.drops.size(),5)
	if game.drops.is_empty():return
	assert_eq(game.drops[0].claim,-1)
	var collector: ArenaRobot=game.robots[0]
	collector.ep=15
	collector.global_position=Vector3(200.4,100,0)
	for drop in game.drops.duplicate():
		collector.global_position=drop.node.global_position-Vector3.UP*0.2
		game.tick_drops(0.001)
	assert_eq(game.drops.size(),0)
	assert_eq(collector.ep,57.0)

func test_energy_depletion_does_not_create_a_drop():
	var game := await make_drop_world()
	var victim: ArenaRobot=game.robots[1]
	victim.ep=0
	game.eliminate(victim,null,"Power depleted")
	game.tick_drops(float(game.corpses[0].time)+0.01)
	assert_eq(game.drops.size(),0)

func test_dropped_core_shares_the_square_cores_actual_materials():
	var square := CoreOrb.new("energy")
	var rounded := CoreOrb.new("energy",true)
	add_child_autofree(square)
	add_child_autofree(rounded)
	var seen := {}
	for mesh in square.visual.find_children("*","MeshInstance3D",true,false):
		for surface in mesh.mesh.get_surface_count():
			var material: Material = mesh.get_active_material(surface)
			seen[Assets.material_role(material.resource_name)] = material
	for mesh in rounded.visual.find_children("*","MeshInstance3D",true,false):
		for surface in mesh.mesh.get_surface_count():
			var material: Material = mesh.get_active_material(surface)
			var role := Assets.material_role(material.resource_name)
			assert_same(material,seen[role],"Rounded and square energy cores share the exact presentation")
	assert_not_null(rounded.visual.find_child("SK_CoreSphereShell",true,false))
	assert_not_null(rounded.visual.find_child("SK_CoreBoltShroud",true,false))

func test_match_physics_creates_and_delivers_core_after_death_hold():
	var game := await make_drop_world()
	var victim: ArenaRobot = game.robots[1]
	var killer: ArenaRobot = game.robots[0]
	killer.ep=10.0
	killer.global_position=Vector3(205,100,0)
	victim.ep=63.5
	assert_true(victim.hit(1000,killer,"pistol"))
	var delay: float = game.corpses[0].time
	game.authority=true
	game.set_physics_process(true)
	await wait_physics_frames(ceili((delay-0.2)*Engine.physics_ticks_per_second))
	assert_eq(game.drops.size(),0,"The live match preserves the corpse hold")
	var observed := false
	for frame in Engine.physics_ticks_per_second*10:
		await wait_physics_frames(1)
		if not game.drops.is_empty():
			observed=true
			assert_true(game.drops[0].node.is_visible_in_tree())
		if observed and game.drops.is_empty(): break
	assert_true(observed,"Observe a live core between corpse removal and homing arrival")
	assert_eq(game.corpses.size(),0)
	assert_eq(game.drops.size(),0)
	assert_eq(killer.ep,73.5,"Normal match physics grants the stored energy exactly once")

func test_scattered_chunks_are_supported_and_spaced_on_a_platform_edge():
	var game := await make_drop_world()
	game.rng.seed=42
	game.spawn_energy_drops(Vector3(203.99,100,0),100.0,-1)
	assert_eq(game.drops.size(),10)
	for index in game.drops.size():
		var point: Vector3=game.drops[index].node.global_position
		assert_lte(point.x+0.125,204.001,"Entire core stays over the platform")
		assert_almost_eq(point.y,100.2,0.001)
		assert_eq(game.drops[index].ep,10.0)
		if index==0: continue
		var nearest := INF
		for previous in index:
			nearest=minf(nearest,point.distance_to(game.drops[previous].node.global_position))
		assert_between(nearest,0.2499,0.3501,"Non-overlapping core has a neighbour 25-35 cm away")

func test_full_killer_leaves_cores_for_eligible_contact_collector():
	var game := await make_drop_world()
	kill_and_wait_for_drop(game)
	var killer: ArenaRobot=game.robots[0]
	killer.ep=100
	killer.global_position=game.drops[0].node.global_position-Vector3.UP*0.2
	game.tick_drops(0.1)
	assert_eq(game.drops.size(),7,"Full killer neither attracts nor consumes cores")
	for drop in game.drops: assert_eq(drop.claim,-1)
	var other: ArenaRobot=game.add_robot(2,"Collector",1,false,"projector")
	other.set_physics_process(false)
	other.protection=0
	other.spawn_remaining=0
	other.ep=97
	other.global_position=killer.global_position
	game.tick_drops(0.001)
	assert_eq(other.ep,100.0)
	assert_eq(game.drops.size(),6,"Collector stops as soon as EP is full")
	assert_eq(killer.ep,100.0)

func test_no_core_is_placed_over_void_without_supported_ground():
	var game := await make_drop_world()
	game.spawn_energy_drops(Vector3(300,100,0),100.0,-1)
	assert_eq(game.drops.size(),0,"Unsupported positions never create floating cores")

func test_each_collected_core_plays_the_item_table_pickup_sound():
	var game := await make_drop_world()
	var killer: ArenaRobot=game.robots[0]
	game.local_robot=killer
	game.audio.set_physics_process(false)
	kill_and_wait_for_drop(game)
	killer.ep=10
	killer.global_position=Vector3(205,100,0)
	for step in 90: game.tick_drops(0.1)
	assert_eq(game.drops.size(),0)
	assert_eq(game.audio.energy_pickups.size(),7,"Each core queues its own pickup transient")
	for step in 150: game.audio._physics_process(1.0/60.0)
	var cues: Array=game.audio.events.filter(func(event):return event.get("id","")=="pickup_item")
	assert_eq(cues.size(),7,"Cluster arrivals are not swallowed by cue cooldown")
	for cue in cues: assert_eq(cue.asset,"world/pickup_item")
	game.tick_drops(0.1)
	assert_true(game.audio.energy_pickups.is_empty(),"Consumed cores never replay")

func test_each_online_core_collection_publishes_one_reliable_pickup_cue():
	var game := await make_drop_world()
	kill_and_wait_for_drop(game)
	game.authority=true
	game.replicating=true
	game.presentation_events.clear()
	var killer: ArenaRobot=game.robots[0]
	killer.ep=10
	killer.global_position=Vector3(205,100,0)
	for step in 90: game.tick_drops(0.1)
	var cues: Array=game.presentation_events.filter(func(event):return event.kind=="audio" and event.cue=="pickup_item")
	assert_eq(cues.size(),7)
	for cue in cues:
		assert_true(cue.individual)
		assert_eq(cue.emitter,killer.robot_id)
	game.authority=false
	var transport := OnlineTransport.new()
	game.add_child(transport)
	transport.game=game
	transport.local_id=killer.robot_id
	for cue in cues: transport.apply_presentation(cue)
	assert_eq(game.audio.energy_pickups.size(),7,"Recipient queues every replicated core cue")
