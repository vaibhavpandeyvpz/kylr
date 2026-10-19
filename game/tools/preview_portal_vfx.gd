extends SceneTree

func _initialize(): build.call_deferred()

func build():
	var stage := Node3D.new()
	root.add_child(stage)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("17202b")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color("d5e4ff")
	environment.environment.ambient_light_energy = 0.7
	environment.environment.glow_enabled = true
	stage.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -25, 0)
	stage.add_child(light)
	var prop := Assets.model("gameplay", "portal_gate")
	stage.add_child(prop)
	Assets.play(prop, "active")
	var fields: Array = []
	for mesh in prop.find_children("*", "MeshInstance3D", true, false):
		if String(mesh.name).contains("Field"):
			fields.append(mesh)
			fields.append(PortalVfx.install(mesh))
	var backdrop := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(0.45, 2.5, 0.45)
	backdrop.mesh = box
	backdrop.position = Vector3(0, 1, -1)
	backdrop.material_override = Assets.material(Color("72808f"))
	stage.add_child(backdrop)
	var camera := Camera3D.new()
	camera.current = true
	camera.fov = 50
	stage.add_child(camera)
	DirAccess.make_dir_recursive_absolute("res://reports")
	for view in [["front", Vector3(1.6, 1.4, 4)], ["back", Vector3(-1.6, 1.4, -4)], ["reduced", Vector3(1.6, 1.4, 4)]]:
		camera.position = view[1]
		camera.look_at(Vector3(0, 0.95, 0))
		PortalVfx.set_reduced_motion(fields, view[0] == "reduced")
		await create_timer(0.25).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://reports/portal-%s.png" % view[0])
	stage.queue_free()
	await process_frame
	quit()
