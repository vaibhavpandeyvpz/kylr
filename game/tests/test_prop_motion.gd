extends GutTest

func test_holder_grips_receiver_band_and_retains_clamp_through_spin():
	var holder := Assets.model("gameplay", "weapon_holder")
	add_child_autofree(holder)
	var payload := Assets.model("weapons", "minigun")
	Assets.socket(holder, "WeaponMount").add_child(payload)
	var width := PropMotion.weapon_grip_width(payload)
	assert_lt(width, 0.05, "The wide barrel housing must not open claws around the narrow receiver")
	var motion := PropMotion.new()
	autofree(motion)
	motion.install(holder)
	motion.set_physics_process(false)
	motion.fit_weapon_grip(width)
	motion.play("deploy", false, "spin", true)
	motion.advance(10.0)
	var bone := motion.skeleton.find_bone("ClawLeft")
	var clamped := motion.skeleton.get_bone_pose_rotation(bone)
	assert_lt(absf(clamped.get_angle()), deg_to_rad(10.0))
	motion.advance(1.5)
	assert_true(clamped.is_equal_approx(motion.skeleton.get_bone_pose_rotation(bone)))
	motion.set_budget(true, 100.0)
	assert_true(clamped.is_equal_approx(motion.skeleton.get_bone_pose_rotation(bone)))

func test_portal_status_uses_only_inner_lenses_and_requires_both_gates_ready():
	var game := ArenaMatch.new()
	game.online = true
	game.authority = false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_loadout()
	game.phase = "Active"
	var portals: Array = []
	for fixture in game.map.fixtures:
		if fixture.kind == "portal": portals.append(fixture)
	assert_gt(portals.size(),1)
	for fixture in portals:
		fixture.motion.set_physics_process(false)
		assert_false(fixture.usable)
		assert_eq(fixture.motion.channels.main.clip,"activate")
		assert_eq(fixture.inner_lights.size(),1,"One isolated inner-lens material surface")
		assert_gt(fixture.inner_lights[0].emission.r,fixture.inner_lights[0].emission.g)
		assert_false(fixture.fields[0].visible)
		assert_eq(fixture.fields.size(), 2, "Retained portal and glow fields")
		assert_same(fixture.fields[0].material_override.shader, PortalVfx.PORTAL)
		assert_eq(fixture.fields[0].transform,fixture.fields[1].transform,"Field layers remain on the same authored plate")
		assert_same(fixture.fields[1].material_override.shader, PortalVfx.GLOW)
		for field in fixture.fields:
			assert_true(field.material_override.shader.resource_path.begins_with("res://shaders/original/"))
			assert_eq(field.material_override.get_shader_parameter("primary_color"), PortalVfx.PRIMARY_COLOR)
			assert_eq(field.material_override.get_shader_parameter("secondary_color"), PortalVfx.SECONDARY_COLOR)
		assert_same(fixture.fields[0].skin, fixture.fields[1].skin, "Glow follows the same animated skeleton")
		for mesh in fixture.node.find_children("*","MeshInstance3D",true,false):
			for surface in mesh.mesh.get_surface_count():
				var material := mesh.get_active_material(surface) as StandardMaterial3D
				if material != null and material.resource_name == "M_Emissive":
					var source := mesh.mesh.surface_get_material(surface) as StandardMaterial3D
					assert_eq(material.emission,source.emission,"Outer strips/header preserve authored lighting through classified material finishes")
					assert_eq(material.emission_energy_multiplier,source.emission_energy_multiplier)
					assert_eq(material.emission_enabled,source.emission_enabled)
		fixture.motion.advance(2.01)
		assert_true(fixture.usable)
		assert_eq(fixture.motion.channels.main.clip,"active")
		fixture.motion.set_budget(true,100.0)
		fixture.motion.advance(1.0)
		assert_true(fixture.usable,"Reduced/distant motion never disables a ready portal")
	game.map._process(0.01)
	for fixture in portals:
		assert_gt(fixture.inner_lights[0].emission.g,fixture.inner_lights[0].emission.r)
		assert_true(fixture.fields[0].visible)
		assert_true(fixture.fields[1].visible)
	game.reduced_motion = true
	game.map._process(0.01)
	for fixture in portals:
		for field in fixture.fields:
			assert_eq(field.material_override.get_shader_parameter("speed_scale"), 0.0)
			assert_true(field.visible, "Reduced Motion preserves ready portals")
	game.phase = "Countdown"
	game.map._process(0.01)
	for fixture in portals:
		assert_gt(fixture.inner_lights[0].emission.r,fixture.inner_lights[0].emission.g,"Ready mechanics remain red until gameplay allows travel")
	game.phase = "Active"
	game.map.start_assembly()
	game.map.shutdown()
	for fixture in portals:
		assert_false(fixture.usable)
		assert_gt(fixture.inner_lights[0].emission.r,fixture.inner_lights[0].emission.g)
		assert_false(fixture.fields[0].visible)
		fixture.motion.advance(4.0)
		assert_eq(fixture.motion.channels.main.clip,"deactivate")
	await wait_process_frames(2)

func test_jumbotron_channels_animate_independently_and_hold_flood_for_results():
	var game := ArenaMatch.new()
	autofree(game)
	game.map = ArenaMap.new()
	autofree(game.map)
	game.map.config = MapCatalog.find("skyfall")
	var asset := Assets.model("environments","jumbotron")
	add_child_autofree(asset)
	var jumbo := JumbotronMotion.new()
	jumbo.install(asset,game)
	jumbo.set_process(false)
	jumbo.motion.set_physics_process(false)
	jumbo.start()
	jumbo.motion.advance(3.21)
	assert_eq(jumbo.motion.channels.rotors.clip,"hover")
	game.phase = "Active"
	jumbo._process(0.3)
	assert_eq(jumbo.motion.channels.spots.clip,"flood","Gameplay lighting holds the authored coverage pose")
	var before := jumbo.motion.skeleton.get_bone_pose_rotation(jumbo.motion.skeleton.find_bone("RotorBackLeft"))
	jumbo.motion.advance(0.31)
	var after := jumbo.motion.skeleton.get_bone_pose_rotation(jumbo.motion.skeleton.find_bone("RotorBackLeft"))
	assert_false(before.is_equal_approx(after),"Steady flood lighting cannot overwrite spinning rotors")
	for light in asset.find_children("*","Light3D",true,false):
		assert_false(light.visible,"Raster defaults leave installed fixture illumination disabled")
		assert_false(light.shadow_enabled)
	game.reduced_motion = true
	jumbo._process(0.3)
	assert_eq(jumbo.motion.channels.spots.clip,"flood")
	game.phase = "Finished"
	game.reduced_motion = false
	jumbo._process(0.3)
	assert_eq(jumbo.motion.channels.rotors.clip,"hover","Results keep the arena alive")
	assert_eq(jumbo.motion.channels.spots.clip,"flood")
	jumbo.shutdown()
	assert_eq(jumbo.motion.channels.rotors.next,"spin_down","Shutdown finishes the current rotor turn")
	jumbo.motion.advance(2.0)
	assert_eq(jumbo.motion.channels.rotors.clip,"spin_down")
	await wait_process_frames(2)

func test_reduced_motion_and_phase_restore_preserve_pickup_state():
	var root := Assets.model("gameplay","item_table")
	add_child_autofree(root)
	var motion := PropMotion.new()
	motion.install(root)
	motion.set_physics_process(false)
	motion.play("spin",true)
	motion.advance(1.3)
	var saved := motion.snapshot()
	var expected := motion.skeleton.get_bone_pose_rotation(motion.skeleton.find_bone("Turntable"))
	motion.advance(0.6)
	motion.restore(saved)
	assert_true(expected.is_equal_approx(motion.skeleton.get_bone_pose_rotation(motion.skeleton.find_bone("Turntable"))),"Restore samples the original phase")
	motion.set_budget(true,100.0)
	assert_eq(motion.channels.main.clip,"spin")
	motion.at_boundary("retract")
	assert_eq(motion.channels.main.clip,"retract","Reduced motion is already at its stable zero-degree pose")
	motion.advance(3.0)
	assert_true(motion.channels.main.done,"Reduced motion still completes one-shot transitions")
	var second := Assets.model("gameplay","item_table")
	add_child_autofree(second)
	var source := Assets.find(second,"AnimationPlayer") as AnimationPlayer
	assert_ne(source.get_animation("spin"),motion.channels.main.player.get_animation("spin"),"Per-instance clocks never modify shared imported animations")

func test_cradles_hold_native_socket_payloads_closed_and_close_before_respawn_reveal():
	var game:=ArenaMatch.new()
	game.map_id="faceoff"
	game.online=true
	game.authority=false
	add_child_autofree(game)
	await get_tree().physics_frame
	await get_tree().physics_frame
	game.map.start_loadout()
	var count:=0
	for fixture in game.map.fixtures:
		if fixture.get("deploy_action","")!="close":continue
		count+=1
		var socket:=Assets.socket(fixture.node,"ItemMount")
		assert_almost_eq(fixture.node.to_local(socket.global_position).y,0.40,0.0001,"Cradle socket sits 10 cm below its 50 cm top")
		assert_same(fixture.payload.get_parent(),socket)
		assert_eq(fixture.payload.transform,Transform3D.IDENTITY,"Payload axes match the authored socket")
		for name in ["ClampFrontLeft","ClampRearLeft","ClampRearRight","ClampFrontRight"]:
			var bone: int=fixture.motion.skeleton.find_bone(name)
			var closed: Animation=fixture.motion.channels.main.player.get_animation("close")
			var track:=closed.find_track(NodePath("Skeleton3D:"+name),Animation.TYPE_ROTATION_3D)
			if track<0:
				for index in closed.get_track_count():
					if closed.track_get_type(index)==Animation.TYPE_ROTATION_3D and String(closed.track_get_path(index)).ends_with(":"+name):track=index;break
			assert_gte(track,0,"Native close clip drives each claw")
			if track>=0:assert_true(fixture.motion.skeleton.get_bone_pose_rotation(bone).is_equal_approx(closed.rotation_track_interpolate(track,closed.length)),"Occupied claws match the native closed pose")
		fixture.motion.advance(1.5)
		fixture.payload.hide();fixture.ready=false;fixture.cooldown=.1
		game.phase="Active"
		game.map.tick(.2)
		assert_false(fixture.payload.visible,"Close claws before revealing a respawned payload")
		fixture.motion.advance(1.5)
		assert_true(fixture.ready)
		assert_true(fixture.payload.visible)
	assert_gt(count,0,"Exercise real Faceoff cradles")
