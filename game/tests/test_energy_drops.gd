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
	assert_eq(game.drops.size(),1,"A bot killed by armor damage leaves its energy")

func test_bot_armor_death_drops_the_remaining_energy_on_the_floor():
	var game := await make_drop_world()
	kill_and_wait_for_drop(game)
	if game.drops.size()!=1:return
	var drop: Dictionary=game.drops[0]
	assert_eq(drop.ep,63.5)
	assert_almost_eq(drop.node.global_position.y,100.2,0.002)
	assert_true(drop.node.is_visible_in_tree())
	assert_not_null(drop.node.visual.find_child("SK_CoreSphereShell",true,false))
	assert_not_null(drop.node.visual.find_child("SK_CoreBoltShroud",true,false))
	game.tick_drops(29.99)
	assert_eq(game.drops.size(),1,"Lifetime starts at appearance, not death")
	game.tick_drops(0.02)
	assert_eq(game.drops.size(),0)

func test_drop_homing_and_collection_use_world_positions():
	var game := await make_drop_world()
	game.effects.position=Vector3(12,0,0)
	game.effects.rotation.y=0.6
	game.effects.scale=Vector3(2,1,2)
	kill_and_wait_for_drop(game)
	if game.drops.size()!=1:return
	var killer: ArenaRobot=game.robots[0]
	killer.ep=10
	killer.global_position=Vector3(205,100,0)
	game.tick_drops(0.1)
	assert_eq(game.drops[0].claim,killer.robot_id,"Nearby killer claims the drop despite its parent's transform")
	for step in 10:game.tick_drops(0.1)
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
	for step in 10:game.tick_drops(0.1)
	assert_eq(game.drops.size(),0)
	assert_eq(killer.ep,73.5)

func test_uncredited_armor_death_leaves_a_contact_collectible_core():
	var game := await make_drop_world()
	var victim: ArenaRobot=game.robots[1]
	victim.ep=42.0
	assert_true(victim.hit(1000,null,"pistol"))
	game.tick_drops(float(game.corpses[0].time)+0.001)
	assert_eq(game.drops.size(),1)
	if game.drops.size()!=1:return
	assert_eq(game.drops[0].claim,-1)
	var collector: ArenaRobot=game.robots[0]
	collector.ep=15
	collector.global_position=Vector3(200.4,100,0)
	game.tick_drops(0.1)
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
	for frame in Engine.physics_ticks_per_second*2:
		await wait_physics_frames(1)
		if not game.drops.is_empty():
			observed=true
			assert_true(game.drops[0].node.is_visible_in_tree())
		if killer.ep>10.0: break
	assert_true(observed,"Observe a live core between corpse removal and homing arrival")
	assert_eq(game.corpses.size(),0)
	assert_eq(game.drops.size(),0)
	assert_eq(killer.ep,73.5,"Normal match physics grants the stored energy exactly once")
