extends SceneTree
const Preparation=preload("res://scripts/core/resource_preparation.gd")

var capture_prefix := "shadow-query"

func _initialize() -> void:
	call_deferred("run")

func capture(material: ShaderMaterial, query: bool, inverted: bool) -> Image:
	ProjectSettings.set_setting("rendering/pathtracing/use_simple_shadows",query)
	material.set_shader_parameter("inverted",inverted)
	if root.get_world_3d().environment.get("pathtracing_enabled"):
		# A populated TLAS does not mean the newly selected shader variant is
		# ready. Let its material/pipeline state update before querying readiness.
		for frame in 2: await RenderingServer.frame_post_draw
		var deadline := Time.get_ticks_msec()+60000
		while RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_TLAS_INSTANCES) < 2:
			if Time.get_ticks_msec() > deadline:
				push_error("Shadow test did not reach a populated RT scene")
				quit(3)
				return Image.new()
			await create_timer(0.1).timeout
		var ready:Dictionary=await Preparation.wait_for_rendering(self,root,true)
		if not ready.ready:
			push_error("Shadow-query variant did not prepare: "+str(ready));quit(3);return Image.new()
		print("SHADOW_QUERY_READY query=",query," inverted=",inverted," ",ready)
	await create_timer(2.0).timeout
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.save_png("res://reports/%s-%s-%s.png" % [capture_prefix,"query" if query else "pipeline","inverted" if inverted else "normal"])
	return image

func difference(a: Image,b: Image) -> float:
	var total := 0.0
	for y in a.get_height():
		for x in a.get_width():
			var first := a.get_pixel(x,y)
			var second := b.get_pixel(x,y)
			total += absf(first.r-second.r)+absf(first.g-second.g)+absf(first.b-second.b)
	return total/(a.get_width()*a.get_height()*3.0)

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture-prefix="):
			capture_prefix=argument.trim_prefix("--capture-prefix=")
	if not capture_prefix.is_valid_filename():
		push_error("Invalid shadow-query capture prefix");quit(2);return
	var raster_only := "--raster-only" in OS.get_cmdline_user_args()
	var raster_first := raster_only or "--raster-first" in OS.get_cmdline_user_args()
	if raster_only: capture_prefix += "-sr-only"
	elif raster_first: capture_prefix += "-transition"
	var device := RenderingServer.get_rendering_device()
	if device == null or not device.has_feature(RenderingDevice.SUPPORTS_RAY_QUERY):
		push_error("Shadow query equivalence requires hardware ray-query support")
		quit(2)
		return
	root.size = Vector2i(800,600)
	root.show()
	root.msaa_3d = Viewport.MSAA_DISABLED
	root.scaling_3d_scale = 0.5
	root.scaling_3d_mode = Viewport.SCALING_3D_MODE_DLSS
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var scene := Node3D.new()
	root.add_child(scene)
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color.BLACK
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_DISABLED
	environment.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	environment.set("pathtracing_enabled",not raster_first)
	environment.set("pathtracing_max_bounces",3)
	environment.set("pathtracing_samples_per_pixel",1)
	environment.set("pathtracing_denoiser",1)
	var world := WorldEnvironment.new()
	world.environment = environment
	scene.add_child(world)
	var floor_mesh := MeshInstance3D.new()
	var plane := BoxMesh.new()
	plane.size = Vector3(12,0.2,12)
	floor_mesh.mesh = plane
	floor_mesh.position.y = -0.1
	var floor_material := StandardMaterial3D.new()
	floor_material.albedo_color = Color(0.7,0.7,0.7)
	floor_material.roughness = 1.0
	floor_mesh.material_override = floor_material
	scene.add_child(floor_mesh)
	var cutout := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2(3,3)
	cutout.mesh = quad
	cutout.position = Vector3(0,1.5,0)
	var shader := Shader.new()
	shader.code = "shader_type spatial; render_mode cull_disabled; uniform bool inverted=false; float mask(vec2 coords){bool hole=mod(floor(coords.x*4.0)+floor(coords.y*4.0),2.0)<1.0; if(hole != inverted) discard; return 1.0;} void fragment(){ ALBEDO=vec3(0.6*mask(UV)); ROUGHNESS=1.0; }"
	var material := ShaderMaterial.new()
	material.shader = shader
	cutout.material_override = material
	scene.add_child(cutout)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-55,-20,0)
	light.light_energy = 2.0
	light.light_angular_distance = 0.0
	light.shadow_enabled = true
	scene.add_child(light)
	var camera := Camera3D.new()
	camera.position = Vector3(4,9,6)
	scene.add_child(camera)
	camera.look_at(Vector3.ZERO)
	camera.make_current()
	camera.far = 100.0
	print("SHADOW_QUERY_CAMERA current=",root.get_camera_3d()==camera," visible=",root.visible)
	if raster_first:
		var raster := await capture(material,false,false)
		raster.save_png("res://reports/%s-raster-sr.png" % capture_prefix)
		if raster_only:
			print("RASTER_SR_PROBE_COMPLETE")
			quit()
			return
		environment.set("pathtracing_enabled",true)
		print("SHADOW_QUERY_RASTER_TO_RT_REQUESTED")
	var pipeline := await capture(material,false,false)
	var pipeline_inverted := await capture(material,false,true)
	var query := await capture(material,true,false)
	var query_inverted := await capture(material,true,true)
	print("SHADOW_QUERY_SCENE env_rt=",environment.get("pathtracing_enabled")," world_rt=",scene.get_world_3d().environment.get("pathtracing_enabled")," tlas=",RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_TLAS_INSTANCES))
	var normal_error := difference(pipeline,query)
	var inverted_error := difference(pipeline_inverted,query_inverted)
	var changed := difference(pipeline,pipeline_inverted)
	print("SHADOW_QUERY_COMPARE normal_mae=",normal_error," inverted_mae=",inverted_error," uniform_change=",changed)
	if normal_error > 0.02 or inverted_error > 0.02 or changed < 0.005:
		push_error("Shadow query fallback failed procedural material equivalence")
		quit(1)
		return
	print("SHADOW_QUERY_EQUIVALENCE_PASS")
	quit()
