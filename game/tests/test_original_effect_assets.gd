extends GutTest

const ROOT := "res://assets/models/effects/combat_effects/"

func test_library_data_texture_channels_survive_export_and_handoff():
	for name in ["combat_effects_rig.json","rocket_cloud_rig.json"]:
		check_data_textures(JSON.parse_string(FileAccess.get_file_as_string(ROOT+name)))

func check_data_textures(manifest: Dictionary) -> void:
	assert_true(manifest.has("texture_samples"),"The source generator records independent channel samples")
	if not manifest.has("texture_samples"): return
	for name in manifest.textures:
		var path: String = ROOT+name
		var imported := ConfigFile.new()
		assert_eq(imported.load(path+".import"),OK)
		assert_true(imported.get_value("params","mipmaps/generate",false))
		assert_false(imported.get_value("params","process/fix_alpha_border",true),"RGBA data channels are independent of transparency")
		assert_false(imported.get_value("params","process/premult_alpha",true))
		assert_eq(FileAccess.get_sha256(path),manifest.textures[name],"Game texture must match its library export")
		var image := Image.new()
		assert_eq(image.load_png_from_buffer(FileAccess.get_file_as_bytes(path)),OK)
		assert_false(image.is_empty())
		for sample in manifest.texture_samples[name]:
			var color := image.get_pixel(int(sample.pixel[0]),int(sample.pixel[1]))
			var channels := [color.r,color.g,color.b,color.a]
			for channel in 4:
				assert_eq(roundi(channels[channel]*255.0),int(sample.rgba8[channel]),"Data channel must not be divided by alpha or converted to sRGB")

func test_effect_kit_delivers_custom_meshes_within_its_authored_budget():
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ROOT+"combat_effects_rig.json"))
	var total := 0
	for id in manifest.triangles:
		var count := int(manifest.triangles[id])
		assert_lte(count,1500)
		total += count
		var mesh := EffectMeshes.mesh(String(id).trim_prefix("SK_"))
		assert_not_null(mesh)
		assert_eq(mesh.get_surface_count(),1)
		assert_true(mesh.get_aabb().position.is_finite())
		assert_true(mesh.get_aabb().size.is_finite())
	assert_lte(total,5000)
	for id in ["FlameEnvelope","VortexSheets","BurstRays"]:
		assert_true(EffectMeshes.mesh(id) is ArrayMesh,"Detailed surfaces come from the authored library kit")

func test_distinct_impact_atlases_survive_handoff_without_empty_or_clipped_cells():
	var hashes: Array[String] = []
	for atlas in ["fireball_atlas","flak_dust_atlas","fire_contact_atlas"]:
		var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ROOT+atlas+"_rig.json"))
		assert_false(hashes.has(manifest.sha256),"Different physical events retain distinct texture content")
		hashes.append(manifest.sha256)
		check_atlas(atlas,manifest)

func test_grenade_is_a_spatial_dust_burst_with_small_ignition():
	var burst := load("res://assets/effects/original/grenade.tscn").instantiate() as OriginalEffect
	add_child_autofree(burst)
	assert_false(burst.has_node("CoolingGas"))
	var dust := 0
	var ignition := 0
	for surface in burst.surfaces:
		assert_ne(surface.node.mesh,EffectMeshes.mesh("AxialCard"))
		assert_eq(surface.role,"spatial_gas")
		assert_ne(int(surface.layer),0,"Grenade has no sustained burning lobes")
		if int(surface.layer) == 3:
			dust += 1
			assert_lt(surface.stretch.y,surface.stretch.x,"Dust spreads along the impact plane")
		else:
			ignition += 1
			assert_lt(float(surface.size),0.6,"Ignition stays compact inside the dust")
	assert_gt(dust,3)
	assert_eq(ignition,1)
	assert_almost_eq(burst.duration,0.9,0.00001)
	burst.set_detail(0)
	var visible_dust := 0
	for surface in burst.surfaces:
		if int(surface.layer)==3 and surface.node.visible: visible_dust += 1
	assert_gt(visible_dust,0)
	assert_lt(visible_dust,dust)

func test_rocket_has_spatial_gas_and_debris_without_camera_facing_cards():
	var burst := load("res://assets/effects/original/rocket.tscn").instantiate() as OriginalEffect
	add_child_autofree(burst)
	assert_false(burst.has_node("CoolingGas"))
	var clouds := 0
	for surface in burst.surfaces:
		var node: MeshInstance3D = surface.node
		assert_ne(node.mesh,EffectMeshes.mesh("AxialCard"),"Rocket layers retain depth from every view")
		assert_gt(node.mesh.get_aabb().size.x,0.01)
		assert_gt(node.mesh.get_aabb().size.y,0.01)
		assert_gt(node.mesh.get_aabb().size.z,0.01)
		if surface.role == "spatial_gas":
			clouds += 1
			assert_not_null(surface.material.get_shader_parameter("albedo_height"))
			assert_not_null(surface.material.get_shader_parameter("normal_roughness"))
	assert_gt(clouds,3,"Several spatial gas regions form a layered blast")
	for emitter in burst.emitters:
		assert_eq(emitter.draw_pass_1,EffectMeshes.mesh("FragmentChip"))
	assert_almost_eq(burst.duration,1.45,0.00001)

func test_rocket_low_detail_keeps_fire_and_soot_and_replay_resets_fade():
	var burst := load("res://assets/effects/original/rocket.tscn").instantiate() as OriginalEffect
	add_child_autofree(burst)
	burst.set_detail(0)
	var layers: Array[int] = []
	var count := 0
	for surface in burst.surfaces:
		if surface.role == "spatial_gas" and surface.node.visible:
			layers.append(int(surface.layer))
			count += 1
	assert_has(layers,0)
	assert_has(layers,1)
	assert_has(layers,2)
	assert_lt(count,9)
	burst.play()
	burst._process(burst.duration)
	assert_false(burst.playing)
	assert_false(burst.visible)
	burst.play()
	assert_true(burst.playing)
	assert_true(burst.visible)
	assert_eq(burst.age,0.0)
	for surface in burst.surfaces:
		assert_eq(surface.node.get_instance_shader_parameter("progress"),0.0)
		assert_true(surface.node.transform.is_finite())

func test_reused_grenade_refreshes_its_world_ignition_origin():
	var burst := load("res://assets/effects/original/grenade.tscn").instantiate() as OriginalEffect
	add_child_autofree(burst)
	for placement in [Transform3D(Basis.IDENTITY,Vector3(3,2,1)),Transform3D(Basis(Vector3.FORWARD,PI/2),Vector3(-4,5,9))]:
		burst.transform = placement
		burst.play()
		var expected := burst.global_position+burst.global_basis.y*0.12
		for surface in burst.surfaces:
			var actual: Vector3 = surface.material.get_shader_parameter("impact_origin")
			assert_lt(actual.distance_to(expected),0.00001,"A pooled ground/wall contact must not retain the previous ignition point")

func check_atlas(atlas: String, manifest: Dictionary) -> void:
	var path := ROOT+atlas+".png"
	var imported := ConfigFile.new()
	assert_eq(imported.load(path+".import"),OK)
	assert_true(imported.get_value("params","mipmaps/generate",false),"Distant color sprites need filtered mip levels")
	assert_eq(FileAccess.get_sha256(path),manifest.sha256)
	var image := Image.new()
	assert_eq(image.load_png_from_buffer(FileAccess.get_file_as_bytes(path)),OK)
	var size := float(manifest.tile_size)
	assert_eq(image.get_size(),Vector2i(int(manifest.atlas_size[0]),int(manifest.atlas_size[1])))
	for frame in 16:
		assert_gt(int(manifest.occupied_pixels[frame]),128,"A successful authoring operator cannot qualify an empty gas frame")
		var column := frame%4
		var row := frame/4
		var origin := Vector2i(roundi(column*size),roundi(row*size))
		var cell_size := Vector2i(roundi((column+1)*size),roundi((row+1)*size))-origin
		var opaque_border_samples := 0
		for offset in range(0,mini(cell_size.x,cell_size.y),8):
			for edge in [Vector2i(offset,0),Vector2i(offset,cell_size.y-1),Vector2i(0,offset),Vector2i(cell_size.x-1,offset)]:
				if image.get_pixelv(origin+edge).a>0.01: opaque_border_samples+=1
		assert_eq(opaque_border_samples,0,"A clipped tile must not become a rectangular volume in game")
