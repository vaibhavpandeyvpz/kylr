extends GutTest

func test_native_fixture_projection_faces_the_authored_room_normal():
	for name in ["bastion","cistern","container","container_long","habitat_pod","hangar","hub","laboratory","lodge","shelter","bunker","lunar_dome"]:
		var prop:=Assets.model("architecture",name)
		add_child_autofree(prop)
		var count:=ArchitectureLights.install(prop,"architecture",name)
		assert_gt(count,0,name+" has native fixtures")
		await get_tree().physics_frame
		var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/architecture/%s/%s_rig.json"%[name,name]))
		var fixtures:=0
		for mount in metadata.gizmos:
			if mount.get("attachment","") not in ["sconce_light","batten_light"]:continue
			fixtures+=1
			var socket:=Assets.socket(prop,mount.name)
			var lamp:=socket.get_node("MountedLuminaire") as Node3D
			assert_eq(lamp.transform,Transform3D.IDENTITY)
			var projection:=Assets.socket(lamp,"LightProjection")
			var normal: Array=mount.mount_normal
			var expected:=Vector3(normal[0],normal[2],-normal[1]).normalized()
			assert_gt((-projection.global_basis.z).normalized().dot(expected),.999,name+" emitter faces into the room")
		assert_eq(fixtures,count)
		if name=="lunar_dome":
			assert_eq(count,1,"Dome uses only its top-center sconce")
			assert_not_null(Assets.socket(prop,"SconceLightMountTopCenter"))

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

func test_ultra_enables_native_rectangles_and_aimed_heads_and_switches_back_live():
	var game := ArenaMatch.new();game.online=true;game.map_id="faceoff"
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.map.start_loadout()
	await wait_physics_frames(3)
	var prefs := Preferences.new("user://ultra_lights_test.cfg")
	for key in Preferences.QUALITY_PRESETS[3]:prefs.values[key]=Preferences.QUALITY_PRESETS[3][key]
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
	for kind in counts:assert_gt(counts[kind],0,kind+" illuminates in Ultra")
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
