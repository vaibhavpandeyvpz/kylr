extends SceneTree

const OUTPUT := "res://reports/core-closeups"
var views: Array[SubViewport] = []
var names: Array[String] = []

func _initialize(): capture.call_deferred()

func capture():
	DirAccess.make_dir_recursive_absolute(OUTPUT)
	for kind in ["energy", "shield", "energy-drop"]:
		for angle in ["front", "angle"]:
			var viewport := SubViewport.new()
			viewport.size = Vector2i(800, 800)
			viewport.own_world_3d = true
			viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
			root.add_child(viewport)
			views.append(viewport)
			names.append(kind + "-" + angle)
			var environment := WorldEnvironment.new()
			environment.environment = Environment.new()
			environment.environment.background_mode = Environment.BG_COLOR
			environment.environment.background_color = Color("111923")
			environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
			environment.environment.ambient_light_color = Color.WHITE
			environment.environment.ambient_light_energy = 0.65
			environment.environment.glow_enabled = true
			viewport.add_child(environment)
			var orb := CoreOrb.new("energy" if kind == "energy-drop" else kind, kind == "energy-drop")
			viewport.add_child(orb)
			var animation := orb.visual.find_child("AnimationPlayer", true, false) as AnimationPlayer
			animation.seek(0.0, true)
			animation.pause()
			var camera := Camera3D.new()
			viewport.add_child(camera)
			camera.position = Vector3(0, 0, 1) if angle == "front" else Vector3(0.65, 0.25, 1)
			camera.look_at(Vector3.ZERO)
			camera.projection = Camera3D.PROJECTION_ORTHOGONAL
			camera.size = 0.20 if kind == "energy-drop" else 0.55
			camera.current = true
	await create_timer(3.0).timeout
	await RenderingServer.frame_post_draw
	for index in views.size():
		var result := views[index].get_texture().get_image().save_png(OUTPUT.path_join(names[index] + "-native.png"))
		if result != OK:
			push_error("Core capture failed: " + names[index])
			quit(1)
			return
	print("CORE_CLOSEUPS_COMPLETE")
	quit()
