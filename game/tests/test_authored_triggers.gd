extends GutTest

func test_plate_and_repair_pad_use_their_rigged_collision_areas():
	for asset in ["pressure_plate", "repair_station"]:
		var prop := Assets.model("gameplay",asset)
		add_child_autofree(prop)
		CollisionRig.install(prop,"gameplay",asset)
		var name := "SK_PressurePlateTrigger" if asset == "pressure_plate" else "SK_RepairStationPadTrigger"
		var area := CollisionRig.install_trigger(prop,"gameplay",asset,name)
		assert_not_null(area)
		if area == null: continue
		assert_true(area.get_parent() is BoneAttachment3D)
		assert_eq(String((area.get_parent() as BoneAttachment3D).bone_name),"Plate" if asset == "pressure_plate" else "Root")
		assert_eq(area.collision_mask,2)
		var body := CharacterBody3D.new()
		body.collision_layer = 2
		var collision := CollisionShape3D.new()
		var capsule := CapsuleShape3D.new()
		capsule.radius = 0.32
		capsule.height = 1.72
		collision.shape = capsule
		collision.position.y = 0.86
		body.add_child(collision)
		add_child_autofree(body)
		await wait_physics_frames(3)
		assert_true(area.overlaps_body(body),asset + " triggers while the robot stands on its authored pad")
		body.position.x = 2.0
		await wait_physics_frames(3)
		assert_false(area.overlaps_body(body),asset + " does not use a broad radial approximation")
		if asset == "repair_station":
			body.position.x = 0.65
			await wait_physics_frames(3)
			assert_false(area.overlaps_body(body),"The old repair stopping distance misses the authored pad")
			body.position.x = 0.35
			await wait_physics_frames(3)
			assert_true(area.overlaps_body(body),"The new repair stopping distance reaches the pad")
		if asset == "pressure_plate":
			var initial_y := area.global_position.y
			var player := Assets.find(prop,"AnimationPlayer") as AnimationPlayer
			Assets.play(prop,"press")
			player.seek(player.current_animation_length,true)
			(Assets.find(prop,"Skeleton3D") as Skeleton3D).force_update_all_bone_transforms()
			await wait_physics_frames(2)
			assert_lt(area.global_position.y,initial_y - 0.035,"Trigger follows the sinking plate bone")
		body.queue_free()
		prop.queue_free()

func test_skyfall_plate_toggles_once_per_entry_and_repair_requires_pad_overlap():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0,true)
	game.map.start_loadout()
	game.phase = "Active"
	var plate: Dictionary
	var station: Dictionary
	for fixture in game.map.fixtures:
		if fixture.kind == "pressure_plate" and plate.is_empty(): plate = fixture
		if fixture.kind == "repair_station" and station.is_empty(): station = fixture
	assert_not_null(plate.get("trigger"))
	assert_not_null(station.get("trigger"))
	assert_eq(station.repair_lights.size(),1,"Repair status has its own material surface")
	game.map.update_repair_status(station)
	var status: StandardMaterial3D = station.repair_lights[0]
	assert_gt(status.emission.g,status.emission.r,"Unoccupied ready bay glows green")
	var native_station := Assets.model("gameplay","repair_station")
	autofree(native_station)
	for mesh in station.node.find_children("*","MeshInstance3D",true,false):
		for surface in mesh.mesh.get_surface_count():
			var material := mesh.get_active_material(surface) as StandardMaterial3D
			if material != null and Assets.material_role(material.resource_name) in ["M_Emissive","M_Shield"]:
				var native_mesh := native_station.find_child(mesh.name,true,false) as MeshInstance3D
				var native_material := native_mesh.get_active_material(surface) as StandardMaterial3D
				assert_eq(material.albedo_color,native_material.albedo_color,"Torch, downlights and shield retain authored colors")
				assert_eq(material.emission,native_material.emission,"Authored emissive surfaces are independent of repair-status feedback")
				assert_eq(material.transparency,native_material.transparency)
	var robot := game.add_robot(0,"Probe",0,true,"projector") as ArenaRobot
	game.local_robot = robot
	robot.protection = 0.0
	robot.position = plate.point + Vector3(0,0.01,0)
	await wait_physics_frames(5)
	assert_true(plate.trigger.overlaps_body(robot))
	assert_true(robot.robot_id in plate.inside)
	var barricade = game.map.fixture_by_id(game.map.config.barricade_links[plate.id])
	assert_not_null(barricade)
	assert_false(barricade.open,"Authored pressure plate entry toggles its barricade")
	await wait_physics_frames(5)
	assert_false(barricade.open,"Standing on the plate cannot toggle repeatedly")
	robot.position = plate.point + Vector3(4,0,0)
	await wait_physics_frames(5)
	assert_true(plate.inside.is_empty())
	robot.position = plate.point + Vector3(0,0.01,0)
	await wait_physics_frames(5)
	assert_true(barricade.open,"A new entry toggles the barricade again")
	robot.ah = 50.0
	robot.position = station.point + Vector3(0,0.01,0)
	robot.velocity = Vector3.ZERO
	robot.listener.global_position = station.point
	await wait_physics_frames(5)
	assert_true(station.trigger.overlaps_body(robot))
	assert_eq(station.occupant,robot,"Repair begins only when the robot reaches the authored pad")
	assert_gt(status.emission.r,status.emission.g,"Activation claims the bay and turns status red immediately")
	assert_true(game.audio.events.any(func(event): return event.get("id", "") == "repair_start_stop" and event.point.distance_to(station.point)<.1),"Shield activation sound originates at the moving repair bay")
	game.authority = false
	robot.set_physics_process(false)
	station.elapsed = 0.0
	game.map.tick_repair(station,1.0)
	assert_gt(status.emission.r,status.emission.g,"Welding remains unavailable to another robot")
	game.map.tick_repair(station,5.0)
	assert_eq(robot.ah,100.0)
	assert_gt(status.emission.r,status.emission.g,"Deactivation remains red")
	game.map.tick_repair(station,1.0)
	assert_null(station.occupant)
	assert_eq(station.cooldown,60)
	assert_gt(status.emission.r,status.emission.g,"The entire recharge remains red")
	game.map.tick(59.9)
	assert_gt(status.emission.r,status.emission.g)
	game.map.tick(0.11)
	assert_gt(status.emission.g,status.emission.r,"Recharge completion restores green")
	game.phase = "Finished"
	game.map.update_repair_status(station)
	assert_gt(status.emission.r,status.emission.g,"Match end disables the bay")
	game.phase = "Active"
	station.occupant = robot
	robot.repair = station
	robot.alive = false
	game.map.tick_repair(station,0.01)
	assert_null(station.occupant)
	assert_eq(station.cooldown,60)
	assert_gt(status.emission.r,status.emission.g,"Interrupted activation/deactivation returns to red recharge")

func test_welding_effects_follow_the_exported_tip_and_only_emit_during_weld_windows():
	var game := ArenaMatch.new()
	game.online = true
	game.authority = false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_loadout()
	game.phase = "Active"
	var station: Dictionary
	for fixture in game.map.fixtures:
		if fixture.kind == "repair_station": station = fixture; break
	var fx: RepairWelding = station.weld_fx
	game.camera.global_position=fx.tip.global_position+Vector3(0,3,5)
	fx.set_process(false)
	var robot := ArenaRobot.new()
	autofree(robot)
	station.occupant = robot
	var player := Assets.find(station.node,"AnimationPlayer") as AnimationPlayer
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	Assets.play(station.node,"repair")
	station.elapsed = 1.2
	game.camera.global_position=fx.tip.global_position+Vector3(0,3,5)
	fx._process(0.01)
	assert_false(fx.glow.visible,"No sparks/glow between welding strokes")
	assert_eq(game.effects.spark_pool.size(),0)
	station.elapsed = 1.6
	player.seek(0.6,true)
	(Assets.find(station.node,"Skeleton3D") as Skeleton3D).force_update_all_bone_transforms()
	await wait_process_frames(2)
	game.camera.global_position=fx.tip.global_position+Vector3(0,3,5)
	fx._process(0.01)
	assert_true(fx.glow.visible)
	assert_eq(fx.glow.get_parent(),fx.tip)
	assert_eq(fx.light.get_parent(),fx.tip)
	assert_eq(game.effects.spark_pool.size(),1,"Welding shares the bounded ballistic spark pool")
	assert_almost_eq(game.effects.spark_pool[0].global_position,fx.tip.global_position,Vector3.ONE*0.001)
	var flash: CombatTransient
	for child in game.effects.get_children():
		if child is CombatTransient: flash = child
	assert_not_null(flash)
	# This test advances the flash manually; a slow render frame must not
	# expire it while the rig's bone transform is being synchronized.
	flash.set_process(false)
	assert_eq(flash.anchor.get_ref(),fx.tip,"Flash is anchored to the live animated gizmo")
	var before := fx.glow.global_position
	player.seek(1.5,true)
	(Assets.find(station.node,"Skeleton3D") as Skeleton3D).force_update_all_bone_transforms()
	await wait_process_frames(2)
	flash._process(0.01)
	assert_false(before.is_equal_approx(fx.glow.global_position),"Rig animation moves the attached glow")
	assert_almost_eq(flash.global_position,fx.tip.global_position,Vector3.ONE*0.001,"Flash follows the rig too")
	game.reduced_motion = true
	var count_before := game.effects.count
	fx._process(0.5)
	assert_true(fx.glow.visible,"Reduced motion retains a steady welding indication")
	assert_eq(game.effects.count,count_before,"Reduced motion suppresses repeated flashes")
	assert_eq(fx.glow.scale,Vector3.ONE)
	station.elapsed = 6.0
	fx._process(0.1)
	assert_false(fx.glow.visible,"Deactivation shuts welding off")
	assert_false(fx.light.visible)
	assert_lte(game.effects.spark_pool.size(),ArenaEffects.MAX_SPARK_BURSTS)
	await wait_process_frames(2)
