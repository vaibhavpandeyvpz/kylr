extends GutTest

func test_native_fixture_projection_faces_the_authored_surface_normal():
	for name in ["bastion","cistern","container","container_long","habitat_pod","hangar","hub","laboratory","lodge","shelter","bunker","lunar_dome"]:
		var prop:=Assets.model("architecture",name)
		add_child_autofree(prop)
		var count:=ArchitectureLights.install(prop,"architecture",name)
		assert_gt(count,0,name+" has native fixtures")
		await get_tree().physics_frame
		var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/architecture/%s/%s_rig.json"%[name,name]))
		var fixtures:=0
		var exterior:=0
		for mount in metadata.gizmos:
			if mount.get("attachment","") not in ["sconce_light","batten_light"]:continue
			fixtures+=1
			if mount.get("surface","")=="exterior":
				exterior+=1
				assert_eq(mount.attachment,"sconce_light")
				var origin: Array=mount.origin
				var outward: Array=mount.mount_normal
				assert_gt(Vector2(origin[0],origin[1]).dot(Vector2(outward[0],outward[1])),0.0,name+" exterior sconce faces away from building")
				if name=="cistern":
					assert_almost_eq(float(origin[1]),0.0,0.0001,"Cistern sconces centre between side buttresses")
					assert_gt(absf(float(outward[0])),0.999)
				if name=="bastion":
					assert_almost_eq(maxf(absf(float(origin[0])),absf(float(origin[1]))),6.9,0.001,"Bastion sconces sit directly on the plain pressure walls")
				if name=="hub":
					assert_gt(float(origin[2]),2.5,"Hub sconces sit on fixed headers above the doors")
				if name in ["hangar","lodge"]:
					assert_gt(absf(float(outward[1])),0.999,name+" exterior sconces belong on front and rear walls")
				if name=="laboratory":
					assert_almost_eq(maxf(absf(float(origin[0])),absf(float(origin[1]))),6.9,0.001,"Laboratory sconces seat directly on all four cleared pressure walls")
					assert_almost_eq(minf(absf(float(origin[0])),absf(float(origin[1]))),3.5,0.001,"Laboratory sconces form symmetric pairs on each wall")
				if name=="habitat_pod":
					assert_almost_eq(float(origin[1]),0.0,0.0001,"Habitat sconces centre along the side panels")
					assert_gt(float(origin[2]),3.0,"Habitat sconces sit above the windows")
					assert_gt(float(outward[2]),0.5,"Habitat sconces follow the sloping upper wall")
			var socket:=Assets.socket(prop,mount.name)
			var lamp:=socket.get_node("MountedLuminaire") as Node3D
			assert_eq(lamp.transform,Transform3D.IDENTITY)
			var projection:=Assets.socket(lamp,"LightProjection")
			var normal: Array=mount.mount_normal
			var expected:=Vector3(normal[0],normal[2],-normal[1]).normalized()
			assert_gt((-projection.global_basis.z).normalized().dot(expected),.999,name+" emitter follows its supported surface normal")
		assert_eq(fixtures,count)
		var expected_exterior: Dictionary={"bastion":8,"bunker":5,"cistern":2,"hangar":4,"lodge":4,"laboratory":8,"hub":4,"habitat_pod":2}
		assert_eq(exterior,int(expected_exterior.get(name,0)),name+" exterior fixtures survive runtime import")
		if name=="lunar_dome":
			assert_eq(count,1,"Dome uses only its top-center sconce")
			assert_not_null(Assets.socket(prop,"SconceLightMountTopCenter"))

func test_faceoff_variants_retain_native_exterior_mounts_and_attach_once():
	var expected_counts: Dictionary={"bastion":8,"hangar":4,"laboratory":8,"lodge":4}
	for asset in expected_counts:
		var suffix: String="_architecture_"+asset
		var prop:=Assets.model("maps","faceoff",suffix)
		add_child_autofree(prop)
		ArchitectureLights.install(prop,"maps","faceoff",suffix)
		var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/faceoff/faceoff%s_rig.json"%suffix))
		var exterior:=0
		for mount in metadata.gizmos:
			if mount.get("surface","")!="exterior":continue
			exterior+=1
			var socket:=Assets.socket(prop,mount.name)
			assert_not_null(socket,asset+" variant retains exterior socket")
			var lamp:=socket.get_node("MountedLuminaire") as Node3D
			assert_eq(lamp.transform,Transform3D.IDENTITY,asset+" sconce uses the native wall frame")
		assert_eq(exterior,int(expected_counts[asset]))
		assert_eq(ArchitectureLights.install(prop,"maps","faceoff",suffix),0,"Repeated installation cannot duplicate lamps")

func test_pole_lamps_are_emissive_only():
	var prop := Assets.model("environments","pole_light")
	add_child_autofree(prop)
	assert_eq(ArchitectureLights.install(prop,"environments","pole_light"),6)
	var lights := prop.find_children("*","Light3D",true,false)
	assert_eq(lights.size(),6)
	for light in lights:
		assert_false(light.visible)
		assert_eq(light.light_cull_mask,0)
		assert_false(light.shadow_enabled)

func test_high_enables_native_rectangles_and_aimed_heads_and_switches_back_live():
	var game := ArenaMatch.new();game.online=true;game.map_id="faceoff"
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_loadout()
	await wait_physics_frames(3)
	var prefs := Preferences.new("user://high_lights_test.cfg")
	for key in Preferences.QUALITY_PRESETS[2]:prefs.values[key]=Preferences.QUALITY_PRESETS[2][key]
	prefs.apply_rendering(game)
	var counts := {"sconce_light":0,"batten_light":0,"pole_light":0,"jumbotron":0}
	for light in game.find_children("*","Light3D",true,false):
		if not light.get_meta("fixture_light",false):continue
		var kind: String=light.get_meta("fixture_kind")
		counts[kind]+=1
		assert_true(light.visible)
		assert_true(light.shadow_enabled)
		assert_gt(light.light_cull_mask,0)
		assert_gt((-light.global_basis.z).normalized().dot((-light.get_parent().global_basis.z).normalized()),.999)
		if kind in ["sconce_light","batten_light"]:assert_true(light is AreaLight3D)
		else:assert_true(light is SpotLight3D)
	for kind in counts:assert_gt(counts[kind],0,kind+" illuminates in High")
	assert_eq(counts.jumbotron,12)
	# Newly attached lights inherit the currently applied preset too.
	var socket := Node3D.new();game.add_child(socket)
	var late := FixtureLighting.spot(socket,"pole_light",{"cone_half_angle_deg":45,"range_m":24})
	assert_true(late.visible)
	assert_true(late.shadow_enabled)
	prefs.values.shadows=false;prefs.apply_rendering(game)
	assert_true(late.visible);assert_false(late.shadow_enabled)
	for key in Preferences.QUALITY_PRESETS[2]:prefs.values[key]=Preferences.QUALITY_PRESETS[2][key]
	prefs.apply_rendering(game)
	for light in game.find_children("*","Light3D",true,false):
		if not light.get_meta("fixture_light",false):continue
		assert_true(light.visible,"High illuminates fixtures")
		assert_true(light.shadow_enabled,"High casts fixture shadows")
		assert_gt(light.light_cull_mask,0)
	# Medium still returns fixtures to their emissive-only presentation.
	for key in Preferences.QUALITY_PRESETS[1]:prefs.values[key]=Preferences.QUALITY_PRESETS[1][key]
	prefs.apply_rendering(game)
	for light in game.find_children("*","Light3D",true,false):
		if not light.get_meta("fixture_light",false):continue
		assert_false(light.visible);assert_false(light.shadow_enabled);assert_eq(light.light_cull_mask,0)

func test_ramparts_and_skyfall_platform_sconces_stay_emissive_only_in_high():
	for map_id in ["ramparts","skyfall"]:
		var game:=ArenaMatch.new()
		game.map_id=map_id;game.online=true;game.authority=false
		add_child_autofree(game)
		while not game.initialization_complete:await wait_process_frames(1)
		var prefs:=Preferences.new("user://platform_sconce_test.cfg")
		for preset in [1,2]:
			prefs.values.merge(Preferences.QUALITY_PRESETS[preset],true)
			prefs.apply_rendering(game)
			var count:=0
			for fixture in game.map.fixtures:
				if fixture.kind!="platform":continue
				for lamp in fixture.node.find_children("MountedLuminaire","Node3D",true,false):
					var meshes: Array=lamp.find_children("*","MeshInstance3D",true,false)
					if not meshes.any(func(mesh):return "Sconce" in String(mesh.name)):continue
					count+=1
					assert_true(lamp.find_children("*","Light3D",true,false).is_empty(),map_id+" sconce emits no projected light")
					for mesh in meshes:assert_eq(mesh.cast_shadow,GeometryInstance3D.SHADOW_CASTING_SETTING_OFF)
			assert_gt(count,0,map_id+" retains visible native sconces")
		game.free()
