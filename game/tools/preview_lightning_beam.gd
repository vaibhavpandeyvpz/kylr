extends SceneTree

var stage: Node3D
var beam: CombatStream
var start := Vector3(1.25, 0, 0)
var end := Vector3(-1.25, 0, 0)

func _initialize():
	call_deferred("build")

func build():
	stage = Node3D.new()
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
	var camera := Camera3D.new()
	camera.position = Vector3(0, 0.8, 4)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 3.2
	camera.current = true
	stage.add_child(camera)
	camera.look_at(Vector3.ZERO)
	beam = CombatStream.new()
	stage.add_child(beam)
	beam.update_endpoints(start, end)
	DirAccess.make_dir_recursive_absolute("res://reports")
	if "--animation" in OS.get_cmdline_user_args():
		for index in 24:
			await create_timer(1.0 / 12.0).timeout
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("res://reports/lightning-beam-frame-%02d.png" % index)
	else:
		await create_timer(0.55).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://reports/lightning-beam.png")
	stage.queue_free()
	await process_frame
	quit()

func _process(_dt: float) -> bool:
	if is_instance_valid(beam): beam.update_endpoints(start, end)
	return false
