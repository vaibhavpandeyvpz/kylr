extends SceneTree

var stage: Node3D
var effects: ArenaEffects
var contact_time := 0.0

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
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -25, 0)
	stage.add_child(light)
	var camera := Camera3D.new()
	camera.position = Vector3(0, 0.6, 3)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 1.7
	camera.current = true
	stage.add_child(camera)
	camera.look_at(Vector3.ZERO)
	var gun := Assets.model("weapons", "lightning_gun")
	gun.position = Vector3(0.25, 0, 0)
	gun.rotation.y = -PI / 2
	stage.add_child(gun)
	for id in ["ArcTip1", "ArcTip2", "ArcTip3"]:
		var sparks := LightningSparks.new()
		sparks.continuous = true
		Assets.socket(gun, id).add_child(sparks)
	var wall := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2(0.5, 0.7)
	wall.mesh = quad
	wall.material_override = Assets.material(Color("39434e"))
	wall.position = Vector3(-0.65, 0, -0.01)
	stage.add_child(wall)
	effects = ArenaEffects.new()
	stage.add_child(effects)
	DirAccess.make_dir_recursive_absolute("res://reports")
	if "--animation" in OS.get_cmdline_user_args():
		for index in 24:
			await create_timer(1.0 / 12.0).timeout
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png("res://reports/lightning-contact-frame-%02d.png" % index)
	else:
		await create_timer(0.12).timeout
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://reports/lightning-contact.png")
	stage.queue_free()
	await process_frame
	quit()

func _process(dt: float) -> bool:
	if is_instance_valid(effects):
		contact_time -= dt
		if contact_time <= 0:
			effects.electric_contact(Vector3(-0.65, 0, 0), Vector3.BACK)
			contact_time = 0.7
	return false
