extends GutTest

func test_regular_spawns_are_inside_cisterns_and_stasis_chambers_are_outside():
	var markers: Array=JSON.parse_string(FileAccess.get_file_as_string(MapCatalog.find("ramparts").metadata)).markers
	for zone in ["A","B"]:
		var spawns: Array=markers.filter(func(m):return m.role=="spawn" and m.zone==zone)
		assert_eq(spawns.size(),5)
		assert_eq(spawns.filter(func(m):return m.asset=="spawn_point" and m.building=="cistern").size(),2)
		assert_eq(spawns.filter(func(m):return m.asset=="stasis_chamber" and m.building==null).size(),3)
		var cistern: Dictionary=markers.filter(func(m):return m.get("source_asset","")=="cistern" and m.zone==zone)[0]
		for spawn in spawns:
			var target: Dictionary=cistern
			if spawn.asset=="spawn_point":
				target=spawns.filter(func(other):return other.asset=="spawn_point" and other.name!=spawn.name)[0]
			var direction:=MapCatalog.vector(target.position_godot)-MapCatalog.vector(spawn.position_godot)
			direction.y=0
			var front:=Vector3.FORWARD if spawn.asset=="spawn_point" else Vector3.BACK
			var facing:=Basis(Vector3.UP,float(spawn.rotation_blender[2]))*front
			assert_gt(facing.dot(direction.normalized()),.9999,"Hatches face each other; chamber doors face the cistern")

func test_indoor_spawn_recesses_cut_the_native_cistern_collision():
	var report: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(MapCatalog.find("ramparts").metadata))
	for zone in ["A","B"]:
		var host: Dictionary=report.markers.filter(func(m):return m.get("source_asset","")=="cistern" and m.zone==zone)[0]
		var cistern:=Assets.model("maps","ramparts",host.asset_suffix)
		add_child_autofree(cistern)
		CollisionRig.install(cistern,"maps","ramparts",null,host.asset_suffix+"_col")
		await wait_physics_frames(2)
		var space:=cistern.get_world_3d().direct_space_state
		var rotation:=Basis(Vector3.UP,float(host.rotation_blender[2]))
		for spawn in report.markers.filter(func(m):return m.role=="spawn" and m.building=="cistern" and m.zone==zone):
			var point:=rotation.inverse()*(MapCatalog.vector(spawn.position_godot)-MapCatalog.vector(host.position_godot))
			assert_true(space.intersect_ray(PhysicsRayQueryParameters3D.create(point+Vector3.UP*.03,point-Vector3.UP*.15,1)).is_empty())
		var solid:=Vector3(0,.07777778,0)
		assert_false(space.intersect_ray(PhysicsRayQueryParameters3D.create(solid+Vector3.UP*.3,solid-Vector3.UP*.15,1)).is_empty())
		cistern.free()

func test_mars_materials_bind_six_distinct_original_pbr_layers():
	assert_eq(MapCatalog.find("ramparts").soil_material,"martian_soil")
	var material:=MartianSoil.material()
	assert_same(material,MartianSoil.material())
	var sources: Dictionary={}
	for layer in MartianSoil.LAYERS:
		var color:=material.get_shader_parameter(layer+"_albedo") as Texture2D
		var normal:=material.get_shader_parameter(layer+"_normal") as Texture2D
		assert_not_null(color);assert_not_null(normal)
		assert_eq(color.get_size(),Vector2(2048,2048))
		sources[color.resource_path]=true
	assert_eq(sources.size(),6,"Separate geological material sources remain distinct")
	assert_not_same(material,MartianSoil.material(true))
	var regolith:=MartianSoil.material(false,true)
	assert_same(regolith,MartianSoil.material(false,true))
	assert_not_same(material,regolith)
	assert_true(regolith.get_shader_parameter("local_surface"),"Platform and prop deposits stay anchored to their object")
	assert_false(material.get_shader_parameter("local_surface"),"Stationary terrain retains geological control maps")

func test_martian_daylight_has_no_pole_light_placements_or_instances():
	var config: Dictionary=MapCatalog.find("ramparts")
	var report: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(config.metadata))
	assert_true(report.markers.filter(func(marker):return marker.asset=="pole_light").is_empty())
	var game:=ArenaMatch.new()
	game.map_id="ramparts";game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	assert_true(game.map.markers.filter(func(marker):return marker.asset=="pole_light").is_empty())
	var sun:=game.map.get_node("LakeSurface/LGT_RampartsSun") as DirectionalLight3D
	assert_gt(sun.light_energy,1.0,"Daytime sunlight illuminates the arena")
	assert_gt(float(config.environment.ambient_energy),.2,"Dusty sky fills the shaded surfaces")

func test_crater_dimensions_and_unplayable_scenery_contact():
	var config: Dictionary=MapCatalog.find("ramparts")
	assert_eq(float(config.crater.diameter_m),150.0)
	assert_eq(float(config.crater.depth_m),15.0)
	assert_true(config.lethal_terrain_contact)
	var game:=ArenaMatch.new()
	game.map_id="ramparts";game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	var space:=game.get_world_3d().direct_space_state
	var floor_hit:=space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(30,3,0),Vector3(30,-20,0),1))
	assert_false(floor_hit.is_empty())
	if floor_hit.is_empty():return
	assert_almost_eq(float(floor_hit.position.y),-15.0,.1)
	assert_true(floor_hit.collider.get_meta("lethal_surface",false))
	var rim_hit:=space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(90,70,0),Vector3(90,-20,0),1))
	assert_false(rim_hit.is_empty())
	if rim_hit.is_empty():return
	assert_gt(float(rim_hit.position.y),10.0)
	assert_true(rim_hit.collider.get_meta("lethal_surface",false))

func test_container_rear_doors_remain_closed_and_repair_bays_face_the_front():
	var game:=ArenaMatch.new()
	game.map_id="ramparts";game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	var count:=0
	for marker in game.map.markers:
		if marker.asset!="container":continue
		assert_eq(marker.open_actions,["front_open"])
		var fixture=game.map.fixture_by_id(marker.name)
		var skeleton:=Assets.find(fixture.node,"Skeleton3D") as Skeleton3D
		var animator:=Assets.find(fixture.node,"AnimationPlayer") as AnimationPlayer
		var closed: Animation=animator.get_animation("rear_close")
		for track in closed.get_track_count():
			var bone_name:=String(closed.track_get_path(track)).get_slice(":",1)
			if not bone_name.begins_with("Rear") or closed.track_get_type(track)!=Animation.TYPE_ROTATION_3D:continue
			var expected: Quaternion=closed.track_get_key_value(track,closed.track_get_key_count(track)-1)
			assert_lt(skeleton.get_bone_pose_rotation(skeleton.find_bone(bone_name)).angle_to(expected),.001)
		var repair: Dictionary=game.map.markers.filter(func(other):return other.role=="repair_station" and other.zone==marker.zone)[0]
		assert_almost_eq(float(repair.rotation_blender[2]),float(marker.rotation_blender[2]),.00001)
		count+=1
	assert_eq(count,2)

func test_rotated_pressure_plate_recess_matches_the_native_footprint():
	var deck:=Assets.model("maps","ramparts","_deck_A_Island")
	add_child_autofree(deck)
	CollisionRig.install(deck,"maps","ramparts",null,"_deck_A_Island_col")
	await wait_physics_frames(2)
	# Plate centre in local deck axes is (0,0, -2.5 Godot Z).
	var hole:=Vector3(.8,0,-2.5)
	var solid:=Vector3(0,0,-3.3)
	var space:=deck.get_world_3d().direct_space_state
	assert_true(space.intersect_ray(PhysicsRayQueryParameters3D.create(hole+Vector3.UP*.2,hole-Vector3.UP*.15,1)).is_empty())
	assert_false(space.intersect_ray(PhysicsRayQueryParameters3D.create(solid+Vector3.UP*.2,solid-Vector3.UP*.15,1)).is_empty())


func test_lake_surface_is_finite_and_faces_upward():
	var water:=LakeSurface.new()
	water.install_water(MapCatalog.find("ramparts").environment)
	for instance: MeshInstance3D in water.get_children():
		var arrays:=instance.mesh.surface_get_arrays(0)
		var vertices: PackedVector3Array=arrays[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array=arrays[Mesh.ARRAY_NORMAL]
		for point in vertices:assert_lte(Vector2(point.x,point.z).length(),75.001,"Lake stays within its 150 m diameter")
		var indices: PackedInt32Array=arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX]!=null else PackedInt32Array()
		var triangle_count:=indices.size()/3 if not indices.is_empty() else vertices.size()/3
		# One sample per quadrant also checks each independently constructed ring strip.
		for triangle in [0,int(triangle_count/4),int(triangle_count/2),int(triangle_count*3/4)]:
			var a: int=indices[triangle*3] if not indices.is_empty() else triangle*3
			var b: int=indices[triangle*3+1] if not indices.is_empty() else triangle*3+1
			var c: int=indices[triangle*3+2] if not indices.is_empty() else triangle*3+2
			assert_lt((vertices[b]-vertices[a]).cross(vertices[c]-vertices[a]).dot(normals[a]),0.0,"Clockwise Godot fronts must face up")
	water.free()
