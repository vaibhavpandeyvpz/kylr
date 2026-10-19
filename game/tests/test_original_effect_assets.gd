extends GutTest

const ROOT := "res://assets/models/effects/combat_effects/"

func test_library_data_texture_channels_survive_export_and_handoff():
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ROOT+"combat_effects_rig.json"))
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
	for atlas in ["fireball_atlas","grenade_atlas","fire_contact_atlas"]:
		var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ROOT+atlas+"_rig.json"))
		assert_false(hashes.has(manifest.sha256),"Different physical events must not silently share the rocket texture")
		hashes.append(manifest.sha256)
		check_atlas(atlas,manifest)

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
