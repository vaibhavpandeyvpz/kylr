extends GutTest

func layout() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(MapCatalog.find("skyfall").metadata))

func test_portals_connect_lower_and_rooftop_within_each_zone():
	var markers := {}
	for marker in layout().markers:
		if marker.role == "portal": markers[marker.name] = marker
	var connected: Array = []
	var pairs: Array = MapCatalog.find("skyfall").portal_pairs
	assert_eq(pairs.size(),2)
	for pair in pairs:
		assert_eq(pair.size(),2)
		var lower: Dictionary = markers[pair[0]]
		var roof: Dictionary = markers[pair[1]]
		assert_eq(lower.zone,roof.zone,"A portal must never cross into the opposing zone")
		assert_eq(lower.level,"lower")
		assert_eq(roof.level,"roof")
		for id in pair:
			assert_false(id in connected,"Every portal has exactly one peer")
			connected.append(id)
	assert_eq(connected.size(),markers.size())

func test_portal_transfers_use_the_same_zone_peer_in_both_directions():
	var game := ArenaMatch.new()
	game.online=true
	game.map_id="skyfall"
	add_child_autofree(game)
	while not game.initialization_complete: await wait_physics_frames(1)
	game.set_physics_process(false)
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0,true)
	game.map.assembly.pause()
	game.map.start_loadout()
	game.phase="Active"
	for fixture in game.map.fixtures:
		if fixture.kind=="portal": fixture.motion.advance(10.0)
	await wait_physics_frames(2)
	var robot: ArenaRobot = game.add_robot(0,"Traveller",0,true,"projector")
	robot.set_physics_process(false)
	robot.set_process(false)
	for pair in game.map.config.portal_pairs:
		for direction in [pair,[pair[1],pair[0]]]:
			var source: Dictionary = game.map.fixture_by_id(direction[0])
			var target: Dictionary = game.map.fixture_by_id(direction[1])
			assert_true(source.usable)
			assert_true(target.usable)
			assert_same(game.map.portal_peer(source.id),target)
			robot.global_position=source.point
			robot.portal_lock=0
			game.map.teleport(source,robot)
			assert_lt(robot.global_position.distance_to(target.point),2.0,"Transfer reaches the intended same-zone gate")
			assert_almost_eq(robot.portal_lock,0.5,0.0001)

func test_mainland_one_upper_barricades_and_controls_are_removed():
	var data := layout()
	for zone in ["A", "B"]:
		var upper: String = zone + "_mainland_1_higher"
		assert_true(data.markers.filter(func(m): return m.deck == upper and m.role in ["barricade", "pressure_plate"]).is_empty())
		for deck in [zone + "_mainland_1_lower", zone + "_mainland_2_higher"]:
			for role in ["barricade", "pressure_plate"]:
				assert_eq(data.markers.filter(func(m): return m.deck == deck and m.role == role).size(), 1)
	assert_eq(MapCatalog.find("skyfall").barricade_links.size(), 4)

func test_removed_upper_fixture_wells_support_physics_rays():
	var model := Assets.model("maps", "skyfall")
	add_child_autofree(model)
	# The placement export's rest pose is the assembled map.
	for marker in layout().markers:
		if marker.role != "platform" or not String(marker.deck).ends_with("mainland_1_higher"):
			continue
		var mount := Assets.socket(model, "Gizmo_" + String(marker.name).replace("-", "_"))
		var deck := Assets.model("maps", "skyfall", marker.asset_suffix)
		mount.add_child(deck)
		CollisionRig.install(deck, "maps", "skyfall", null, marker.asset_suffix + "_col")
	await wait_physics_frames(2)
	for sign in [-1.0, 1.0]:
		for x in [14.0, 17.0]:
			var point := Vector3(sign * x, 26, sign * 22.5)
			var query := PhysicsRayQueryParameters3D.create(point + Vector3.UP * .1, point - Vector3.UP * .1, 1)
			var hit := model.get_world_3d().direct_space_state.intersect_ray(query)
			assert_false(hit.is_empty(), "Former upper barricade/plate well is solid: %s" % point)
			if not hit.is_empty(): assert_almost_eq(float(hit.position.y), 26.0, .001)

func test_lunar_surface_has_no_playable_placements_or_navigation():
	assert_true(MapCatalog.find("skyfall").lunar_surface_lethal)
	for height in MapCatalog.find("skyfall").navigation.levels: assert_gte(height,22)
	for marker in layout().markers:
		assert_true(marker.zone != "common" or marker.role == "jumbotron" or marker.get("budget_excluded",false),String(marker.name))
	for link in MapCatalog.find("skyfall").drop_links: assert_gte(link.to[1],22)

func test_wall_pickup_axes_are_authored_into_gizmos():
	var model := Assets.model("maps","skyfall")
	add_child_autofree(model)
	await wait_process_frames(1)
	for marker in layout().markers:
		if not marker.get("wall_mounted",false): continue
		var mount := Assets.socket(model,"Gizmo_"+String(marker.name).replace("-","_"))
		assert_not_null(mount)
		var contact := Assets.socket(model,marker.pickup_contact_gizmo)
		assert_not_null(contact)
		var target := contact.global_position-mount.global_position
		target.y=0
		# Blender's mounting-plane +Z normal becomes Godot's local +Y.
		assert_gt(mount.global_basis.y.normalized().dot(target.normalized()),0.99999,String(marker.name))

func test_container_opens_only_rear_native_rig():
	var model := Assets.model("architecture","container")
	add_child_autofree(model)
	await wait_process_frames(1)
	var map := ArenaMap.new()
	autofree(map)
	var player := Assets.find(model,"AnimationPlayer") as AnimationPlayer
	Assets.play(model,"front_close")
	player.seek(player.current_animation_length,true)
	player.pause()
	var skeleton := Assets.find(model,"Skeleton3D") as Skeleton3D
	var closed := {}
	for name in ["LeftDoor","RightDoor","RearLeftDoor","RearRightDoor"]:closed[name]=skeleton.get_bone_pose_rotation(skeleton.find_bone(name))
	map.open_architecture(model,["rear_open"])
	skeleton.force_update_all_bone_transforms()
	for name in ["LeftDoor","RightDoor"]:
		assert_true(skeleton.get_bone_pose_rotation(skeleton.find_bone(name)).is_equal_approx(closed[name]),name+" stays closed")
	for name in ["RearLeftDoor","RearRightDoor"]:
		var change: Quaternion = closed[name].inverse()*skeleton.get_bone_pose_rotation(skeleton.find_bone(name))
		assert_almost_eq(minf(change.get_angle(),TAU-change.get_angle()),deg_to_rad(105),0.001,name+" is open")

func test_long_container_opens_both_native_ends():
	var model := Assets.model("architecture","container_long")
	add_child_autofree(model)
	await wait_process_frames(1)
	var map := ArenaMap.new()
	autofree(map)
	var player := Assets.find(model,"AnimationPlayer") as AnimationPlayer
	Assets.play(model,"front_close")
	player.seek(player.current_animation_length,true)
	player.pause()
	var skeleton := Assets.find(model,"Skeleton3D") as Skeleton3D
	var closed := {}
	for name in ["LeftDoor","RightDoor","RearLeftDoor","RearRightDoor"]:closed[name]=skeleton.get_bone_pose_rotation(skeleton.find_bone(name))
	map.open_architecture(model,["front_open","rear_open"])
	skeleton.force_update_all_bone_transforms()
	for name in ["LeftDoor","RightDoor","RearLeftDoor","RearRightDoor"]:
		var change: Quaternion = closed[name].inverse()*skeleton.get_bone_pose_rotation(skeleton.find_bone(name))
		assert_almost_eq(minf(change.get_angle(),TAU-change.get_angle()),deg_to_rad(105),0.001,name)

func test_ammo_pairs_have_twenty_centimetre_origin_spacing():
	var markers: Array = layout().markers
	for left in markers:
		if left.role != "ammo" or not String(left.name).ends_with("-L"):continue
		var right_name := String(left.name).trim_suffix("-L")+"-R"
		var right := markers.filter(func(m):return m.name==right_name)
		assert_eq(right.size(),1)
		assert_almost_eq(MapCatalog.vector(left.position_godot).distance_to(MapCatalog.vector(right[0].position_godot)),0.2,0.0001)

func test_platforms_use_shared_map_helpers_and_pulse_guns_are_disabled_in_dm():
	var platforms := 0
	for marker in layout().markers:
		if marker.role != "platform":continue
		platforms+=1
		assert_eq(marker.category,"maps")
		assert_eq(marker.asset,"skyfall")
		assert_true(FileAccess.file_exists("res://assets/models/maps/skyfall/skyfall%s.glb"%marker.asset_suffix))
	assert_eq(platforms,20)
	assert_eq(MapCatalog.find("skyfall").pulse_gun.enabled_match_types,["TDM","CTF"])

func test_thrusters_attach_to_authorized_native_platform_sockets():
	var game:=ArenaMatch.new()
	game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_map_assembly()
	game.map.assembly.seek(5,true)
	game.map.assembly.pause()
	await wait_physics_frames(3)
	game.map.start_loadout()
	await wait_physics_frames(2)
	var count:=0
	for marker in layout().markers:
		if marker.role!="thruster":continue
		var platform=game.map.fixture_by_id(marker.parent_fixture)
		var thruster=game.map.fixture_by_id(marker.name)
		var native_mount:=Assets.socket(platform.node,marker.parent_socket)
		assert_not_null(native_mount)
		assert_eq(thruster.node.get_parent(),native_mount)
		assert_almost_eq(thruster.node.transform.origin,Vector3.ZERO,Vector3.ONE*0.00001)
		assert_true(thruster.node.transform.basis.is_equal_approx(Basis.IDENTITY))
		assert_almost_eq(native_mount.global_position,MapCatalog.vector(marker.position_godot),Vector3.ONE*0.0001)
		count+=1
	assert_eq(count,16)

func test_floor_heights_and_tapered_bases_meet_lunar_clearance():
	assert_lte(layout().total_map_triangles,layout().triangle_budget)
	assert_eq(layout().level_surface_z_m,{"common":0.0,"lower":22.0,"higher":26.0,"roof":30.0})
	var bottom:=INF
	for marker in layout().markers:
		if marker.role!="platform" or not marker.underbody:continue
		var path: String="res://assets/models/maps/skyfall/skyfall%s_rig.json"%marker.asset_suffix
		var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(path))
		bottom=minf(bottom,float(marker.position_godot[1])-float(metadata.depth_m))
		assert_almost_eq(float(metadata.depth_m)-0.8,1.5,0.00001)
		assert_gte(float(marker.position_godot[1])-float(metadata.depth_m),15.0)
	assert_almost_eq(bottom,19.7,0.00001)

func test_map_budget_counts_castings_and_mounting_geometry_only():
	var data:=layout()
	var total: int=int(data.triangles)
	for marker in data.markers:
		if marker.role!="platform":continue
		var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/skyfall/skyfall%s_rig.json"%marker.asset_suffix))
		assert_eq(metadata.recess_clearance_per_side_m,0.001)
		total+=int(metadata.triangles)
	assert_eq(total,int(data.total_map_triangles))
	assert_eq(data.recess_clearance_per_side_m,0.001)
	var model:=Assets.model("maps","skyfall")
	add_child_autofree(model)
	for mesh in model.find_children("*","MeshInstance3D",true,false):
		assert_true(String(mesh.name).begins_with("SK_SkyfallWall_") or String(mesh.name).begins_with("SK_SkyfallPillarPad_"),String(mesh.name))
	var scenery: Array=data.markers.filter(func(marker):return marker.name=="lunar-scenery")
	assert_eq(scenery.size(),1)
	assert_true(scenery[0].load_at_start)
	assert_not_null(Assets.socket(model,"Gizmo_lunar_scenery"))

func test_native_platform_luminaire_models_use_their_projection_sockets():
	var marker: Dictionary=layout().markers.filter(func(m):return m.role=="platform" and m.helper_family=="platform" and m.size_m==[25.0,25.0])[0]
	var platform:=Assets.model("maps","skyfall",marker.asset_suffix)
	add_child_autofree(platform)
	await wait_process_frames(1)
	var count:=ArchitectureLights.install(platform,"maps","skyfall",marker.asset_suffix)
	assert_gt(count,0)
	for lamp in platform.find_children("MountedLuminaire","Node3D",true,false):
		assert_not_null(Assets.socket(lamp,"LightProjection"))
		assert_true(lamp.transform.is_equal_approx(Transform3D.IDENTITY))
	assert_eq(ArchitectureLights.install(platform,"maps","skyfall",marker.asset_suffix),0,"Repeated installation is idempotent")

func test_native_bottom_supports_and_wall_holders_use_identity_socket_attachments():
	var game:=ArenaMatch.new()
	game.map_id="skyfall";game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.assembly.seek(5,true);game.map.assembly.pause()
	game.map.start_loadout()
	await wait_physics_frames(2)
	var pillars:=0
	var pads:=0
	var walls:=0
	for marker in game.map.markers:
		if marker.asset=="pillar_platform":pads+=1
		if marker.asset=="weapon_holder_wall":walls+=1
		if marker.get("parent_socket","") not in ["PillarMountTop","WeaponHolderMount"]:continue
		var fixture: Dictionary=game.map.fixture_by_id(marker.name+marker.parent_socket if marker.role=="weapon" else marker.name)
		var parent: Dictionary=game.map.fixture_by_id(marker.parent_fixture)
		assert_eq(fixture.node.get_parent(),Assets.socket(parent.node,marker.parent_socket))
		assert_true(fixture.node.transform.is_equal_approx(Transform3D.IDENTITY))
		if marker.role=="pillar":
			pillars+=1
			assert_almost_eq(fixture.node.global_position.y,marker.position_blender[2]+1,0.0001)
			var skeleton:=Assets.find(fixture.node,"Skeleton3D") as Skeleton3D
			skeleton.force_update_all_bone_transforms()
			var head:=skeleton.get_bone_global_pose(skeleton.find_bone("Stage2"))
			assert_almost_eq((skeleton.global_transform*(head*Vector3(0,1.5,0))).y,marker.position_blender[2]+3.2,0.001)
	assert_eq(pads,pillars,"Exactly one bottom block per pillar")
	assert_eq(walls,8,"All eight current Figma wall mounts are imported")
