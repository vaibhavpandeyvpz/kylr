extends GutTest

func test_core_pickups_preserve_native_cube_and_symbol_materials():
	for kind in ["energy", "shield"]:
		var orb := CoreOrb.new(kind)
		add_child_autofree(orb)
		await wait_process_frames(2)
		assert_not_null(orb.visual.find_child("SK_CoreGlassLayer1",true,false))
		assert_not_null(orb.visual.find_child("SK_CoreCornerArmor",true,false))
		assert_not_null(orb.visual.find_child("SK_CoreBoltShroud" if kind=="energy" else "SK_CoreShieldShroud",true,false))
		assert_null(orb.visual.find_child("OrbLayers",true,false),"No replacement sphere hides the native cube")
		for mesh in orb.visual.find_children("*","MeshInstance3D",true,false):
			assert_true(mesh.visible)
			assert_null(mesh.material_override,"Retain library materials")
func assembled_ctf() -> ArenaMatch:
	var game := ArenaMatch.new()
	game.online = true
	game.match_type = "CTF"
	add_child_autofree(game)
	return game

func test_map_is_complete_before_five_second_countdown():
	var game := assembled_ctf()
	await wait_physics_frames(3)
	game.begin_countdown()
	assert_true(game.map_assembly_finished)
	assert_false(game.map.assembly.is_playing())
	assert_true(game.loadout_started)
	assert_true(game.spawn_reveal_started)
	assert_gt(game.map.fixtures.size(),0)
	game._physics_process(4.9)
	assert_eq(game.phase,"Countdown")
	game._physics_process(0.1)
	assert_eq(game.phase,"Active")
	assert_eq(game.elapsed,0.0)
func test_flag_uses_ground_mount_cloth_tint_and_authored_loops():
	var game := assembled_ctf()
	game.set_physics_process(false)
	await wait_physics_frames(3)
	game.begin_countdown()
	game._physics_process(ArenaMatch.ARENA_RISE_SECONDS)
	game._physics_process(ArenaMatch.MAP_ASSEMBLY_SECONDS)
	await wait_physics_frames(2)
	for team in 2:
		var flag: Dictionary = game.flags[team]
		assert_true(flag.node.visible)
		var mount := Assets.socket(flag.node,"GroundMount")
		assert_not_null(mount)
		assert_almost_eq(mount.global_position,flag.point,Vector3.ONE * 0.02)
		var tinted := false
		for mesh in flag.node.find_children("*","MeshInstance3D",true,false):
			for surface in mesh.mesh.get_surface_count():
				var material := mesh.get_active_material(surface) as StandardMaterial3D
				if material != null and Assets.material_role(material.resource_name) == "M_Flag":
					assert_true(material.albedo_color.is_equal_approx(game.team_colors[team]))
					tinted = true
				elif material != null and Assets.material_role(material.resource_name) in ["M_Primary","M_Secondary"]:
					assert_false(material.albedo_color.is_equal_approx(game.team_colors[team]),"Flag hardware retains its authored finish")
		assert_true(tinted,"Only the cloth has the team material override")
	await wait_seconds(0.9)
	var player := Assets.find(game.flags[0].node,"AnimationPlayer") as AnimationPlayer
	assert_true(String(player.current_animation).ends_with("wave"))
	var flag: Dictionary = game.flags[0]
	flag.state = "carried"
	Assets.play(flag.node,"stow")
	await wait_seconds(1.0)
	assert_true(String(player.current_animation).ends_with("flutter"))
	game.reset_flag_home(flag)
	await wait_seconds(0.9)
	assert_true(String(player.current_animation).ends_with("wave"))

func test_flag_lands_on_surface_and_returns_home_when_no_playable_surface_exists():
	var game := assembled_ctf()
	await wait_physics_frames(3)
	game.begin_countdown()
	game._physics_process(ArenaMatch.ARENA_RISE_SECONDS)
	game._physics_process(ArenaMatch.MAP_ASSEMBLY_SECONDS)
	await wait_physics_frames(2)
	var flag: Dictionary = game.flags[0]
	flag.node.global_position = flag.home + Vector3.UP * 6.0
	game.drop_carried_flag(flag,flag.node.global_position,false)
	assert_eq(flag.state,"dropped")
	assert_true(flag.falling)
	for step in 10: game.tick_flags(0.3)
	assert_false(flag.falling)
	assert_almost_eq(Assets.socket(flag.node,"GroundMount").global_position,flag.point,Vector3.ONE * 0.02)
	game.drop_carried_flag(flag,Vector3(200,10,200),false)
	assert_eq(flag.state,"home")
	var scenery := StaticBody3D.new()
	scenery.collision_layer = 1
	game.add_child(scenery)
	scenery.global_position = game.map.world_point([40,0,0])
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(4,0.4,4)
	shape.shape = box
	scenery.add_child(shape)
	await wait_physics_frames(2)
	game.drop_carried_flag(flag,scenery.global_position + Vector3.UP * 4.0,false)
	assert_eq(flag.state,"home","A nearby collider outside the playable footprint cannot trap the flag")

func test_energy_drop_uses_authored_core_model_and_spin():
	var orb := CoreOrb.new("energy",true)
	add_child_autofree(orb)
	await wait_process_frames(2)
	assert_not_null(orb.visual.find_child("SK_CoreSphereShell",true,false))
	assert_not_null(orb.visual.find_child("SK_CoreBoltShroud",true,false))
	var player := Assets.find(orb.visual,"AnimationPlayer") as AnimationPlayer
	assert_not_null(player)
	if player: assert_true(String(player.current_animation).ends_with("spin"))

func test_both_core_pickups_follow_authored_item_mounts():
	var game := assembled_ctf()
	await wait_physics_frames(3)
	game.begin_countdown()
	game._physics_process(ArenaMatch.ARENA_RISE_SECONDS)
	game._physics_process(ArenaMatch.MAP_ASSEMBLY_SECONDS)
	await wait_physics_frames(2)
	var counts := {"energy":0,"shield":0}
	for fixture in game.map.fixtures:
		if fixture.kind not in counts: continue
		counts[fixture.kind] += 1
		assert_true(fixture.payload is CoreOrb)
		assert_eq(fixture.payload.kind,fixture.kind)
		assert_true(fixture.payload.get_parent().name.begins_with("ItemMount"))
		var shape := "SK_CoreBoltShroud" if fixture.kind == "energy" else "SK_CoreShieldShroud"
		assert_not_null(fixture.payload.visual.find_child(shape,true,false))
	assert_eq(counts.energy,game.map.markers.filter(func(m):return m.role=="energy").size())
	assert_eq(counts.shield,game.map.markers.filter(func(m):return m.role=="shield").size())

func test_core_outer_and_inner_rig_spin_in_opposite_directions():
	for kind in ["energy","shield"]:
		var orb := CoreOrb.new(kind)
		add_child_autofree(orb)
		await wait_process_frames(2)
		var player := Assets.find(orb.visual,"AnimationPlayer") as AnimationPlayer
		var skeleton := Assets.find(orb.visual,"Skeleton3D") as Skeleton3D
		assert_not_null(player)
		assert_not_null(skeleton)
		if player == null or skeleton == null: continue
		var clip := player.current_animation
		player.seek(0.0,true)
		var outer_rest := skeleton.get_bone_pose_rotation(skeleton.find_bone("Outer"))
		var inner_rest := skeleton.get_bone_pose_rotation(skeleton.find_bone("Inner"))
		player.seek(player.get_animation(clip).length * 0.25,true)
		var outer := outer_rest.inverse() * skeleton.get_bone_pose_rotation(skeleton.find_bone("Outer"))
		var inner := inner_rest.inverse() * skeleton.get_bone_pose_rotation(skeleton.find_bone("Inner"))
		assert_true((outer * inner).is_equal_approx(Quaternion.IDENTITY),kind + " bones counter-rotate")

func test_corpse_and_energy_drop_settle_on_the_platform_below():
	var game := assembled_ctf()
	await wait_physics_frames(3)
	game.begin_countdown()
	game._physics_process(ArenaMatch.ARENA_RISE_SECONDS)
	game._physics_process(ArenaMatch.MAP_ASSEMBLY_SECONDS)
	await wait_physics_frames(2)
	game.phase = "Active"
	var victim := game.add_robot(0,"Falling",0,true,"projector") as ArenaRobot
	var platform := StaticBody3D.new()
	platform.collision_layer = 1
	game.add_child(platform)
	platform.global_position = game.flags[0].home + Vector3.UP * 3.0
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(4,0.4,4)
	shape.shape = box
	platform.add_child(shape)
	await wait_physics_frames(2)
	victim.global_position = platform.global_position + Vector3.UP * 5.0
	victim.last_safe = game.flags[0].home
	victim.ah = 0
	victim.ep = 48
	game.eliminate(victim,null,"rifle")
	assert_eq(game.corpses.size(),1)
	var landing: Vector3 = game.corpses[0].point
	assert_gt(landing.y,3.0,"Nearest platform, not the lower ground, catches the corpse")
	for step in 10: game.tick_drops(0.5)
	assert_eq(game.drops.size(),1)
	if game.drops.size() == 1:
		assert_true(game.drops[0].node is CoreOrb)
		assert_almost_eq(game.drops[0].node.global_position.y,landing.y + 0.2,0.02)
