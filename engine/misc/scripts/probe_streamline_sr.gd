extends SceneTree
## Standalone primitive-scene SR reproduction, independent of any application.
## A nonblank image is not image-quality or performance qualification.

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	var output:=""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="):output=arg.trim_prefix("--output=")
	if not output.is_empty():DirAccess.make_dir_recursive_absolute(output)
	var cases:Array=[]
	if not Engine.has_singleton("Streamline") or not Engine.get_singleton("Streamline").get_capability(0):
		push_error("Streamline Super Resolution is unavailable")
		quit(2)
		return
	print("STREAMLINE_SR_FIXTURE_CAPABILITIES sr=", Engine.get_singleton("Streamline").get_capability(0),
		" rr=", Engine.get_singleton("Streamline").get_capability(2))
	root.size = Vector2i(640, 360)
	root.msaa_3d = Viewport.MSAA_DISABLED
	root.use_taa = false
	root.scaling_3d_mode = Viewport.SCALING_3D_MODE_DLSS
	var stage := Node3D.new()
	root.add_child(stage)
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR
	world.environment.background_color = Color(0.04, 0.05, 0.07)
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color = Color(0.2, 0.2, 0.2)
	stage.add_child(world)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.position = Vector3(0, 2, 5)
	camera.look_at(Vector3(0, 0.6, 0))
	camera.current = true
	var light := DirectionalLight3D.new()
	stage.add_child(light)
	light.rotation_degrees = Vector3(-50, -30, 0)
	light.shadow_enabled = true
	var floor_node := MeshInstance3D.new()
	var floor_mesh := PlaneMesh.new()
	floor_mesh.size = Vector2(12, 12)
	floor_node.mesh = floor_mesh
	stage.add_child(floor_node)
	var sphere := MeshInstance3D.new()
	sphere.mesh = SphereMesh.new()
	sphere.position.y = 0.7
	stage.add_child(sphere)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.1, 0.3, 0.7)
	material.roughness = 0.3
	sphere.material_override = material
	for scale in [0.5, 1.0]:
		root.scaling_3d_scale = scale
		print("STREAMLINE_SR_BEGIN scale=", scale)
		for frame in 48:
			await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		if image.is_empty():
			push_error("Empty SR viewport")
			quit(3)
			return
		var minimum:=1.0;var maximum:=0.0;var energy:=0.0
		for y in 9:
			for x in 16:
				var color:=image.get_pixel(int((x*2+1)*image.get_width()/32.0),int((y*2+1)*image.get_height()/18.0))
				var luminance:=color.get_luminance()
				minimum=minf(minimum,luminance);maximum=maxf(maximum,luminance);energy+=luminance
		if maximum-minimum<.02 or energy/144.0<.01:
			push_error("SR fixture output has no meaningful scene variation");quit(3);return
		if root.scaling_3d_mode!=Viewport.SCALING_3D_MODE_DLSS or not is_equal_approx(root.scaling_3d_scale,scale):
			push_error("Requested SR viewport configuration was not retained");quit(3);return
		if not output.is_empty() and image.save_png(output.path_join("scale-"+str(scale)+".png"))!=OK:quit(3);return
		cases.append({"scale":scale,"scaling_mode":root.scaling_3d_mode,"size":[image.get_width(),image.get_height()],"minimum_luminance":minimum,"maximum_luminance":maximum,"mean_grid_luminance":energy/144.0})
		print("STREAMLINE_SR_END scale=", scale)
	stage.queue_free()
	for frame in 6:
		await process_frame
	if not output.is_empty():
		FileAccess.open(output.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({"fixture_completed":true,"cases":cases,"sr_supported":Engine.get_singleton("Streamline").get_capability(0),"rr_supported":Engine.get_singleton("Streamline").get_capability(2),"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),"probe_sha256":FileAccess.get_sha256(get_script().resource_path),"quality_accepted":false,"performance_accepted":false},"\t"))
	print("STREAMLINE_SR_FIXTURE_COMPLETE")
	quit()
