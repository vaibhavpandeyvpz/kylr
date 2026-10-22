extends GutTest

func test_fireball_contact_is_compact_volumetric_and_flame_dominant():
	var burst := load("res://assets/effects/original/fire_hit.tscn").instantiate() as OriginalEffect
	add_child_autofree(burst)
	var layers := [0,0,0,0,0]
	var flares := 0
	for surface in burst.surfaces:
		if surface.role=="fuel_flare":
			flares += 1
			assert_ne(surface.node.mesh,EffectMeshes.mesh("AxialCard"))
			assert_not_null(surface.material.get_shader_parameter("flow_material"))
			assert_not_null(surface.material.get_shader_parameter("flow_relief"))
			continue
		assert_eq(surface.role,"spatial_gas")
		assert_same(surface.node.mesh,EffectMeshes.mesh("ThermalShell"))
		assert_lt(float(surface.size),0.8,"Fuel burst stays smaller than rocket lobes")
		assert_eq(surface.material.shader.resource_path,"res://shaders/original/fireball_contact_3d.gdshader")
		assert_not_null(surface.material.get_shader_parameter("normal_roughness"))
		layers[int(surface.layer)] += 1
	assert_eq(layers,[0,1,1,0,3],"Three faint inner volumes, one wisp and one ignition core")
	assert_eq(flares,6,"Six independently curling and eroding flame membranes form the flare cloud")
	assert_true(burst.emitters.is_empty(),"Fuel contacts contain neither sprite particles nor debris")
	assert_almost_eq(burst.duration,0.48,0.00001)
	burst.play()
	burst._process(burst.duration)
	assert_false(burst.visible)
	burst.play()
	assert_true(burst.visible,"Pooled contacts restart cleanly")

const ROOT := "res://assets/models/effects/combat_effects/"

func test_library_data_texture_channels_survive_export_and_handoff():
	for name in ["combat_effects_rig.json","rocket_cloud_rig.json","muzzle_flow_rig.json","fireball_material_rig.json"]:
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
	for id in ["FlameEnvelope","VortexSheets","FragmentChip"]:
		assert_true(EffectMeshes.mesh(id) is ArrayMesh,"Detailed surfaces come from the authored library kit")

func test_flak_dust_atlas_survives_handoff_without_empty_or_clipped_cells():
	var atlas := "flak_dust_atlas"
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ROOT+atlas+"_rig.json"))
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
			assert_eq(surface.stretch,Vector3.ONE,"Dust expands volumetrically without flattening")
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
	assert_eq(visible_dust,dust,"Low detail preserves complete spherical coverage")

func test_blast_clouds_expand_as_spheres_instead_of_axial_or_planar_shapes():
	for kind in ["rocket","grenade","fall_impact"]:
		var burst := load("res://assets/effects/original/"+kind+".tscn").instantiate() as OriginalEffect
		add_child_autofree(burst)
		burst.play()
		burst.set_process(false)
		var previous_extent := Vector3.ZERO
		for age in [0.01,0.05,0.15]:
			burst.age = age
			burst._process(0.0)
			var low := Vector3.ONE*INF
			var high := Vector3.ONE*-INF
			for surface in burst.surfaces:
				if not surface.get("spherical",false): continue
				var node: MeshInstance3D = surface.node
				assert_almost_eq(node.scale.x,node.scale.y,0.00001)
				assert_almost_eq(node.scale.x,node.scale.z,0.00001)
				low = low.min(node.position-node.scale*0.48)
				high = high.max(node.position+node.scale*0.48)
			var extent := high-low
			assert_almost_eq(extent.x,extent.y,0.00001,kind+" spherical Y extent")
			assert_almost_eq(extent.x,extent.z,0.00001,kind+" spherical Z extent")
			assert_gt(extent.x,previous_extent.x,"The complete volume grows over time")
			previous_extent = extent
	for incoming in [Vector3.DOWN,Vector3(1,-2,3),Vector3.LEFT]:
		var axis := ArenaEffects.blast_axis(Vector3.UP,incoming)
		assert_gt(axis.dot(-incoming.normalized()),0.9999,"Full 3D flight defines the orientation frame")

func test_muzzle_profile_controls_inner_and_outer_dimensions_and_colors():
	var burst := load("res://assets/effects/original/flash_long.tscn").instantiate() as OriginalEffect
	add_child_autofree(burst)
	var profile := MuzzleFlashProfile.new()
	profile.outer_color = Color.RED
	profile.jet_color = Color.CYAN
	profile.outer_radius = 0.12
	profile.jet_radius = 0.04
	profile.outer_length = 0.6
	profile.jet_length = 0.85
	profile.emission = 3.0
	burst.configure_muzzle(profile)
	assert_eq(burst.surfaces.size(),4,"Envelope, inner jet, crown and curled sheets form the flash")
	assert_eq(burst.get_node("MuzzleFlare").mesh,EffectMeshes.mesh("FlameEnvelope"),"Outer layer uses an open lofted surface")
	assert_eq(burst.get_node("MuzzleCrown").mesh,EffectMeshes.mesh("PressureRing"),"The front rim has a hole rather than a closing cap")
	for surface in burst.surfaces:
		assert_ne(surface.node.mesh,EffectMeshes.mesh("AxialCard"))
		assert_eq(surface.material.get_shader_parameter("outer_color"),Color.RED)
		assert_eq(surface.material.get_shader_parameter("jet_color"),Color.CYAN)
		assert_eq(surface.material.get_shader_parameter("outer_radius"),0.12)
		assert_eq(surface.material.get_shader_parameter("jet_radius"),0.04)
		assert_eq(surface.material.get_shader_parameter("outer_length"),0.6)
		assert_eq(surface.material.get_shader_parameter("jet_length"),0.85)
		assert_not_null(surface.material.get_shader_parameter("flow_material"))
		assert_almost_eq(surface.node.custom_aabb.end.x,0.85,0.00001)
	burst.configure_muzzle(profile,0.425)
	assert_eq(profile.outer_length,0.6,"Fitting a flash never mutates its shared profile")
	assert_almost_eq(burst.surfaces[0].material.get_shader_parameter("outer_length"),0.3,0.00001)

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
	assert_eq(count,13,"Six fire and six soot volumes plus the core retain spherical coverage")
	for surface in burst.surfaces:
		if surface.role == "spatial_gas":
			assert_eq(surface.material.get_shader_parameter("march_steps"),16,"Low detail reduces volumetric samples")
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
