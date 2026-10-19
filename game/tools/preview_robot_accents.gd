extends SceneTree

func _initialize() -> void: run.call_deferred()

func run() -> void:
	root.size = Vector2i(1600,900)
	var stage := Node3D.new()
	root.add_child(stage)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("101822")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = .6
	stage.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35,-30,0)
	stage.add_child(light)
	var camera := Camera3D.new()
	camera.position = Vector3(0,1,8)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 7.8
	camera.current = true
	stage.add_child(camera)
	var colors := [Color("ecb846"),Color("689649"),Color("3878b4"),Color("b74740")]
	var names := ["YELLOW / BLUE","OLIVE / TAN","BLUE / YELLOW","RED / SAND"]
	for i in colors.size():
		var body := Assets.model("characters","tensor")
		stage.add_child(body)
		body.position.x = (i-1.5)*1.85
		var accent := Assets.robot_accent(body,colors[i],"tensor")
		assert(not accent.is_equal_approx(colors[i]))
		Assets.paint(body,colors[i],accent,"projector")
		for mesh: MeshInstance3D in body.find_children("*","MeshInstance3D",true,false):
			for surface in mesh.mesh.get_surface_count():
				var material := mesh.get_active_material(surface) as StandardMaterial3D
				if material != null and Assets.material_role(material.resource_name) == "M_Secondary": assert(material.albedo_color.is_equal_approx(accent))
		var label := Label3D.new()
		label.text = names[i]
		label.position = Vector3(body.position.x,2.15,0)
		label.pixel_size = .002
		label.font_size = 26
		stage.add_child(label)
	await create_timer(2).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/robot-accents.png")
	print("ROBOT_ACCENTS_PASS")
	quit()
