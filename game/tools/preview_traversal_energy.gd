extends SceneTree
## Native render checks for closed energy geometry, including exactly edge-on.
func _initialize() -> void:
	build.call_deferred()

func build() -> void:
	root.size = Vector2i(1100,700)
	var stage := Node3D.new()
	root.add_child(stage)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("17202b")
	stage.add_child(environment)
	var camera := Camera3D.new()
	camera.current = true
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 1.2
	stage.add_child(camera)
	DirAccess.make_dir_recursive_absolute("res://reports/traversal-energy")
	for kind in ["ring","arrow"]:
		var instance := MeshInstance3D.new()
		instance.mesh = TraversalEnergyMesh.square_ring() if kind == "ring" else TraversalEnergyMesh.chevron()
		assert(is_equal_approx(instance.mesh.get_aabb().size.y,0.02))
		var material := ShaderMaterial.new()
		material.shader = load("res://shaders/jump_pad_energy_pulse.gdshader" if kind == "ring" else "res://shaders/speed_ramp_energy_arrows.gdshader")
		material.set_shader_parameter("motion_speed",0.0)
		material.set_shader_parameter("phase_offset",0.35 if kind == "ring" else 0.45)
		instance.material_override = material
		stage.add_child(instance)
		var centre := Vector3(0,0.35,0) if kind == "ring" else Vector3(0,0,0.7)
		for view in ["angle","side"]:
			camera.position = centre + (Vector3(1,0.8,1.4) if view == "angle" else Vector3(2,0,0))
			camera.look_at(centre)
			await create_timer(0.2).timeout
			await RenderingServer.frame_post_draw
			var image := root.get_texture().get_image()
			image.save_png("res://reports/traversal-energy/%s-%s.png" % [kind,view])
		instance.queue_free()
		await process_frame
	stage.queue_free()
	await process_frame
	print("PASS traversal energy: 2 cm meshes; angled and edge-on captures")
	quit()
