extends SceneTree

func _initialize() -> void:
	call_deferred("probe")

func probe() -> void:
	var game := ArenaMatch.new()
	game.online=true
	game.third_person=true
	root.add_child(game)
	await physics_frame
	await physics_frame
	game.phase="Active"
	game.goal=1000
	game.time_limit=10000
	game.set_process(false)
	game.camera_rig.set_process(false)
	var floor := StaticBody3D.new()
	var collision := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size=Vector3(120,0.2,120)
	collision.shape=box
	floor.add_child(collision)
	floor.position=Vector3(100,-0.1,0)
	root.add_child(floor)
	var deck := MeshInstance3D.new()
	var deck_mesh := BoxMesh.new()
	deck_mesh.size=box.size
	deck.mesh=deck_mesh
	deck.material_override=Assets.material(Color("38424b"))
	floor.add_child(deck)
	var camera := Camera3D.new()
	root.add_child(camera)
	camera.current=true
	var robot: ArenaRobot=game.add_robot(0,"Movement probe",0,true,"projector")
	robot.spawn_remaining=0
	robot.protection=0
	robot.show()
	var output: Array=[]
	var capture := "--capture" in OS.get_cmdline_user_args()
	var shield_preview := "--shield" in OS.get_cmdline_user_args()
	if shield_preview: robot.sh=100; robot.shield_time=1000
	var stages := ["run","crouch","fire_run","hit_fire","jump_fire"] if shield_preview else ["run", "strafe", "crouch", "sprint", "fire_run", "reload_run", "hit_fire", "hit_reload", "jump", "charged_jump", "jump_fire", "jump_reload", "fall", "launch", "blocked"]
	for stage in stages:
		robot.position=Vector3(100,0.01,0)
		robot.velocity=Vector3.ZERO
		robot.yaw=0
		robot.previous_yaw=0
		robot.wants_fire=false
		robot.wants_sprint=false
		robot.wants_crouch=false
		robot.reload_time=0
		robot.hit_flash=0
		robot.ah=1000
		robot.jump_held=false
		robot.jump_release=false
		robot.jump_charge=0
		robot.movement_pose.reset()
		robot.move_input=Vector2.ZERO
		for frame in 4: await physics_frame
		if stage=="fall": robot.position.y=6
		robot.move_input=Vector2.RIGHT if stage=="strafe" else Vector2.UP
		robot.wants_crouch=stage=="crouch"
		robot.wants_sprint=stage=="sprint"
		robot.pickup_weapon="minigun" if stage in ["fire_run","hit_fire","jump_fire"] else "rifle"
		robot.loaded=100
		robot.packs=1
		robot.equip(robot.pickup_weapon)
		robot.wants_fire=stage in ["fire_run","hit_fire","jump_fire"]
		if stage in ["reload_run","hit_reload","jump_reload"]: robot.loaded=10; robot.start_reload()
		var wall: StaticBody3D
		if stage=="blocked":
			wall=StaticBody3D.new()
			var shape := CollisionShape3D.new()
			var wall_box := BoxShape3D.new()
			wall_box.size=Vector3(4,4,0.2)
			shape.shape=wall_box
			wall.add_child(shape)
			wall.position=Vector3(100,2,-1.0)
			root.add_child(wall)
		var leg := robot.skeleton.find_bone("LeftUpperLeg")
		var last_rotation := robot.skeleton.get_bone_pose_rotation(leg)
		var changing := 0
		var moving := 0
		var active_fire := 0
		var mismatch := 0
		var air_frames := 0
		var falling_frames := 0
		var jump_loop_frames := 0
		var reaction_frames := 0
		var reload_interruptions := 0
		for frame in 120:
			if frame==5:
				if stage in ["jump","jump_fire","jump_reload"]: robot.jump_buffer=ArenaTuning.JUMP_BUFFER
				if stage=="charged_jump": robot.jump_charge=ArenaTuning.CHARGE_SECONDS; robot.jump_release=true
				if stage=="launch": robot.apply_knockback(Knockback.impulse(Vector3.FORWARD,11,8))
			if frame%20==10 and stage in ["hit_fire","hit_reload"]: robot.hit(1,null,"probe")
			await physics_frame
			camera.position=robot.position+(Vector3(1.5,1.3,2.2) if shield_preview else Vector3(3.0,1.6,4.0))
			camera.look_at(robot.position+Vector3.UP*0.95)
			var rotation := robot.skeleton.get_bone_pose_rotation(leg)
			if not rotation.is_equal_approx(last_rotation): changing+=1
			if robot.measured_speed>0.2:
				moving+=1
				if robot.is_on_floor() and not robot.movement_pose.key.contains("walk_") and not robot.movement_pose.key.contains("run_") and not robot.movement_pose.key.contains("sprint_"): mismatch+=1
			if not robot.is_on_floor(): air_frames+=1
			if robot.movement_pose.key=="common/falling": falling_frames+=1
			if robot.movement_pose.key.ends_with("/jump_loop"): jump_loop_frames+=1
			if robot.hit_flash>0: reaction_frames+=1
			if robot.reload_time>0 and not robot.anim_state.ends_with("/reload"): reload_interruptions+=1
			if robot.anim_state.ends_with("/fire"): active_fire+=1
			last_rotation=rotation
			if capture and frame in [30,45,60,75] and (shield_preview or stage in ["fire_run","strafe","crouch","jump_fire","fall","hit_fire"]):
				await process_frame
				await RenderingServer.frame_post_draw
				root.get_texture().get_image().save_png("res://reports/movement_%s%s_%d.png" % ["shield_" if shield_preview else "",stage,frame])
		output.append({"stage":stage,"moving_frames":moving,"leg_changes":changing,"fire_frames":active_fire,"air_frames":air_frames,"jump_loop_frames":jump_loop_frames,"falling_frames":falling_frames,"reaction_frames":reaction_frames,"reload_interruptions":reload_interruptions,"mismatch":mismatch,"final_clip":robot.movement_pose.key,"final_speed":robot.measured_speed})
		if mismatch>2: push_error("Movement pose mismatch: "+stage); quit(1); return
		if stage=="fire_run" and (active_fire<80 or changing<80): push_error("Fire froze locomotion"); quit(1); return
		if reload_interruptions>0: push_error("Movement/hit interrupted reload: "+stage); quit(1); return
		if stage in ["jump","charged_jump","jump_fire","jump_reload"] and (air_frames<15 or jump_loop_frames<15 or falling_frames>0): push_error("Intentional jump used falling pose: "+stage); quit(1); return
		if stage in ["fall","launch"] and (air_frames<15 or falling_frames<5): push_error("Missing airborne transition: "+stage); quit(1); return
		if stage=="blocked" and not robot.movement_pose.key.ends_with("/idle"): push_error("Blocked robot runs in place"); quit(1); return
		if is_instance_valid(wall): wall.queue_free()
	print("MOVEMENT_ANIMATION_PROBE ",JSON.stringify(output))
	game.phase="Finished"
	for voice in game.audio.voices: voice.stop()
	OS.delay_msec(100)
	game.queue_free()
	floor.queue_free()
	camera.queue_free()
	for frame in 3: await physics_frame
	quit()
