extends SceneTree

const TILE = Vector2i(384, 320)

func scenes_in(directory: String) -> Array[String]:
	var result: Array[String] = []
	var folder := DirAccess.open(directory)
	for file in folder.get_files():
		if file.ends_with(".tscn"): result.append(directory.path_join(file))
	for child in folder.get_directories(): result.append_array(scenes_in(directory.path_join(child)))
	result.sort()
	return result

func _initialize() -> void:
	render_catalog.call_deferred()

func render_catalog() -> void:
	var manifest := {}
	var folders := {"original":"res://assets/effects/original"}
	var only_pack := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--pack="): only_pack = argument.trim_prefix("--pack=")
	DirAccess.make_dir_recursive_absolute("res://reports/vfx-contact-sheets")
	for pack in folders:
		manifest[pack] = scenes_in(folders[pack])
	var output_manifest := FileAccess.open("res://reports/vfx-contact-sheets/manifest.json", FileAccess.WRITE)
	output_manifest.store_string(JSON.stringify(manifest, "\t"))
	for pack in folders:
		if only_pack != "" and only_pack != pack: continue
		var paths: Array = manifest[pack]
		for page in ceili(paths.size() / 9.0):
			var tiles: Array[SubViewport] = []
			var compositions: Array[Node3D] = []
			for index in range(page * 9, mini(paths.size(), (page + 1) * 9)):
				var viewport := SubViewport.new()
				viewport.size = TILE
				viewport.own_world_3d = true
				viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
				root.add_child(viewport)
				tiles.append(viewport)
				var env := WorldEnvironment.new()
				env.environment = Environment.new()
				env.environment.background_mode = Environment.BG_COLOR
				env.environment.background_color = Color("202936")
				env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
				env.environment.ambient_light_color = Color.WHITE
				env.environment.ambient_light_energy = 0.5
				env.environment.glow_enabled = true
				viewport.add_child(env)
				var light := DirectionalLight3D.new()
				light.rotation_degrees = Vector3(-40, -30, 0)
				light.light_energy = 1.0
				viewport.add_child(light)
				var camera := Camera3D.new()
				viewport.add_child(camera)
				camera.position = Vector3(6, 4, 8)
				camera.look_at(Vector3(0, 0.5, 0))
				camera.projection = Camera3D.PROJECTION_ORTHOGONAL
				camera.size = 7.5
				if String(paths[index]).get_file().begins_with("flash"): camera.size = 2.7
				camera.current = true
				# Background landmarks expose transparency and distortions.
				for column in range(-3, 4):
					var box := MeshInstance3D.new()
					var geometry := BoxMesh.new()
					geometry.size = Vector3(0.08, 5, 0.08)
					box.mesh = geometry
					box.position = Vector3(column, 0.5, -3)
					box.material_override = Assets.material(Color("5b6c7d"))
					viewport.add_child(box)
				var composition := PackVfx.instantiate(load(paths[index]) as PackedScene)
				viewport.add_child(composition)
				PackVfx.apply_palette(composition)
				PackVfx.play_once(composition)
				compositions.append(composition)
				if composition is OriginalEffect:
					composition.age = composition.duration * 0.12
					composition._process(0.0)
					composition.set_process(false)
				for particle in composition.find_children("*", "GPUParticles3D", true, false):
					particle.emitting = true
					particle.restart()
				var label := Label.new()
				label.text = String(paths[index]).get_file().get_basename()
				label.position = Vector2(8, 287)
				label.add_theme_font_size_override("font_size", 18)
				viewport.add_child(label)
			var sheet := Image.create(TILE.x * 6, TILE.y * 3, false, Image.FORMAT_RGBA8)
			sheet.fill(Color("101820"))
			# Hold the authored phase during shader compilation. Otherwise a
			# brief muzzle flash can finish before its first rendered frame.
			await create_timer(1.0).timeout
			await RenderingServer.frame_post_draw
			for index in tiles.size():
				var pixels := tiles[index].get_texture().get_image()
				pixels.convert(Image.FORMAT_RGBA8)
				sheet.blit_rect(pixels, Rect2i(Vector2i.ZERO, TILE), Vector2i((index % 3) * TILE.x * 2, (index / 3) * TILE.y))
			for composition in compositions:
				if composition is OriginalEffect:
					composition.age = composition.duration * 0.65
					composition._process(0.0)
					composition.set_process(false)
			await create_timer(0.1).timeout
			await RenderingServer.frame_post_draw
			for index in tiles.size():
				var pixels := tiles[index].get_texture().get_image()
				pixels.convert(Image.FORMAT_RGBA8)
				sheet.blit_rect(pixels, Rect2i(Vector2i.ZERO, TILE), Vector2i((index % 3) * TILE.x * 2 + TILE.x, (index / 3) * TILE.y))
			var output := "res://reports/vfx-contact-sheets/%s-%02d.png" % [pack, page + 1]
			sheet.save_png(output)
			print("CONTACT_SHEET ", output)
			for viewport in tiles:
				viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
				viewport.queue_free()
			await process_frame
			await RenderingServer.frame_post_draw
	print("CATALOG_COMPLETE")
	quit()
