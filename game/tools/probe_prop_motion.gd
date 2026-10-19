extends SceneTree
## Render real map fixtures and authored attachments at controlled machinery states.
func _initialize() -> void:
	call_deferred("probe")

func capture(camera: Camera3D, target: Node3D, offset: Vector3, tag: String) -> void:
	camera.global_position = target.global_position + offset
	camera.look_at(target.global_position + Vector3.UP)
	for frame in 4: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/machinery_"+tag+".png")
	print("MACHINERY_CAPTURE ",tag)

func probe() -> void:
	var game := ArenaMatch.new()
	game.online = true
	game.authority = false
	root.add_child(game)
	await physics_frame
	await physics_frame
	game.set_process(false)
	game.camera_rig.set_process(false)
	game.map.start_assembly()
	var arena_player := Assets.find(game.map.stadium,"AnimationPlayer") as AnimationPlayer
	arena_player.seek(4.0,true)
	arena_player.pause()
	game.map.assembly.seek(5.0,true)
	game.map.start_loadout()
	game.camera_rig.host.set_process(false)
	var camera := Camera3D.new()
	root.add_child(camera)
	camera.current = true
	camera.fov = 48
	game.camera = camera
	var portal: Dictionary
	var holder: Dictionary
	var station: Dictionary
	for fixture in game.map.fixtures:
		if fixture.kind == "portal" and portal.is_empty(): portal = fixture
		if fixture.kind == "weapon" and holder.is_empty(): holder = fixture
		if fixture.kind == "repair_station" and station.is_empty(): station = fixture
	for motion in game.map.machinery: motion.set_physics_process(false)
	game.map.jumbotron.motion.set_physics_process(false)
	game.map.jumbotron.set_process(false)
	await capture(camera,portal.node,Vector3(2.4,1.5,4.0),"portal_unusable")
	for motion in game.map.machinery: motion.advance(3.3)
	game.phase = "Active"
	game.map._process(0.1)
	await capture(camera,portal.node,Vector3(2.4,1.5,4.0),"portal_usable")
	holder.motion.advance(1.0)
	await capture(camera,holder.node,Vector3(2.2,2.0,3.0),"holder_spin")
	holder.payload.hide()
	holder.ready = false
	holder.cooldown = 60.0
	holder.motion.at_boundary("retract")
	holder.motion.advance(4.0)
	holder.motion.advance(2.0)
	await capture(camera,holder.node,Vector3(2.2,2.0,3.0),"holder_retracted")
	game.map.update_repair_status(station)
	var repair_player := Assets.find(station.node,"AnimationPlayer") as AnimationPlayer
	repair_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	repair_player.play("deactivate",0.0)
	repair_player.seek(1.0,true)
	await capture(camera,station.node,Vector3(3.3,2.4,4.2),"repair_ready")
	var patient: ArenaRobot = game.add_robot(0,"Repair patient",0,true,"projector")
	patient.set_physics_process(false)
	patient.set_process(false)
	patient.global_position = Assets.socket(station.node,"PlayerMount").global_position
	patient.pose("common/idle")
	patient.animator.play("common_idle",0.0)
	patient.animator.advance(0.0)
	patient.skeleton.force_update_all_bone_transforms()
	patient.attach_gun()
	patient.repair = station
	station.occupant = patient
	station.elapsed = 0.5
	game.map.update_repair_status(station)
	repair_player.play("activate",0.0)
	repair_player.seek(0.5,true)
	await capture(camera,station.node,Vector3(3.3,2.4,4.2),"repair_activating")
	station.elapsed = 1.6
	game.map.update_repair_status(station)
	repair_player.play("activate",0.0)
	repair_player.seek(1.0,true)
	repair_player.play("repair",0.0)
	repair_player.seek(0.6,true)
	await capture(camera,station.node,Vector3(3.3,2.4,4.2),"repair_welding")
	station.elapsed = 6.3
	repair_player.play("deactivate",0.0)
	repair_player.seek(0.3,true)
	# Let emitted sparks complete after emission stops at the welding boundary.
	for frame in 24: await process_frame
	await capture(camera,station.node,Vector3(3.3,2.4,4.2),"repair_deactivating")
	game.map.release_repair(station)
	patient.animator.advance(0.2)
	patient.attach_gun()
	repair_player.seek(1.0,true)
	await capture(camera,station.node,Vector3(3.3,2.4,4.2),"repair_recharging")
	game.map.set_repair_geometry_valid(station,false)
	await capture(camera,station.node,Vector3(3.3,2.4,4.2),"repair_unavailable")
	var jumbo := game.map.jumbotron
	jumbo.motion.advance(3.3)
	jumbo._process(0.3)
	jumbo.motion.advance(1.0)
	await capture(camera,jumbo.motion.asset,Vector3(12,2,14),"jumbotron_active")
	game.result = {"title":"Team A wins"}
	game.phase = "Finished"
	jumbo._process(0.3)
	await capture(camera,jumbo.motion.asset,Vector3(12,2,14),"jumbotron_results")
	game.free()
	camera.free()
	await process_frame
	quit()
