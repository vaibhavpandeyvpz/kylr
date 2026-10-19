extends SceneTree
## Verify Light3D.shadow_enabled on the actual path tracer, not raster shadows.
## Generic scene: occluder, matte floor and one light. No application assets.
var output := ""
var query_shadows := false

func _initialize(): run.call_deferred()

func color_average(image: Image, pixel: Vector2) -> Vector3:
	var total := Vector3.ZERO
	for y in range(roundi(pixel.y)-3,roundi(pixel.y)+4):
		for x in range(roundi(pixel.x)-3,roundi(pixel.x)+4):
			var color := image.get_pixel(x,y)
			total += Vector3(color.r,color.g,color.b)
	return total/49.0

func luminance(image: Image, pixel: Vector2) -> float:
	return color_average(image,pixel).dot(Vector3(.2126,.7152,.0722))

func ready() -> bool:
	var started := Time.get_ticks_msec()
	var stable := 0
	while Time.get_ticks_msec()-started < 60000:
		await process_frame
		await RenderingServer.frame_post_draw
		var valid := RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_SCENE_READY)>0
		var pending := RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_PENDING_MATERIALS)
		stable = stable+1 if valid and pending==0 else 0
		if stable>=8: return true
	return false

func run():
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output=argument.trim_prefix("--output=")
		if argument.begins_with("--query-shadows="): query_shadows=argument.trim_prefix("--query-shadows=")=="1"
	if output.is_empty() or DisplayServer.get_name()=="headless":quit(2);return
	if query_shadows and not RenderingServer.get_rendering_device().has_feature(RenderingDevice.SUPPORTS_RAY_QUERY):push_error("Ray queries unavailable");quit(2);return
	ProjectSettings.set_setting("rendering/pathtracing/use_simple_shadows",query_shadows)
	if FileAccess.file_exists(output.path_join("report.json")):push_error("Preserve previous results");quit(2);return
	if DirAccess.make_dir_recursive_absolute(output)!=OK:quit(2);return
	root.size=Vector2i(640,360)
	root.scaling_3d_mode=Viewport.SCALING_3D_MODE_BILINEAR
	root.scaling_3d_scale=1.0
	root.msaa_3d=Viewport.MSAA_DISABLED
	root.use_taa=false
	var stage := Node3D.new();root.add_child(stage)
	var world := WorldEnvironment.new();world.environment=Environment.new();stage.add_child(world)
	world.environment.background_mode=Environment.BG_COLOR
	world.environment.background_color=Color.BLACK
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_DISABLED
	world.environment.set("pathtracing_enabled",true)
	world.environment.set("pathtracing_denoiser",0)
	world.environment.set("pathtracing_max_bounces",1)
	world.environment.set("pathtracing_samples_per_pixel",8)
	var material := StandardMaterial3D.new()
	material.albedo_color=Color(.4,.4,.4);material.roughness=1.0;material.metallic_specular=0.0
	var floor_shape := PlaneMesh.new();floor_shape.size=Vector2(16,16)
	var floor_mesh := MeshInstance3D.new();floor_mesh.mesh=floor_shape;floor_mesh.material_override=material;stage.add_child(floor_mesh)
	var box := MeshInstance3D.new();box.mesh=BoxMesh.new();box.position=Vector3(0,.5,0);box.material_override=material;stage.add_child(box)
	var camera := Camera3D.new();stage.add_child(camera);camera.current=true
	camera.position=Vector3(3,4,-5);camera.look_at(Vector3(.4,0,-.6))
	var cases := []
	var passed := true
	for kind in ["omni","spot","directional","area"]:
		var light: Light3D
		match kind:
			"omni":
				var omni := OmniLight3D.new();omni.omni_range=20;light=omni
			"spot":
				var spot := SpotLight3D.new();spot.spot_range=20;spot.spot_angle=45;light=spot
			"directional": light=DirectionalLight3D.new()
			"area":
				var area := AreaLight3D.new();area.area_range=20;area.area_size=Vector2(.15,.15);area.area_normalize_energy=true;light=area
		light.position=Vector3(-2,4,2)
		light.light_energy=1.0 if kind=="directional" else 40.0
		light.light_size=0.0
		stage.add_child(light);light.look_at(Vector3.ZERO)
		var phases := []
		for enabled in [true,false,true]:
			light.shadow_enabled=enabled
			if not await ready():push_error("Shadow fixture not ready");quit(3);return
			var image := root.get_texture().get_image()
			if image.get_size()!=Vector2i(640,360):push_error("Unexpected output dimensions");quit(3);return
			var name := "%s-%d-%s.png"%[kind,phases.size(),str(enabled)]
			if image.save_png(output.path_join(name))!=OK:quit(3);return
			phases.append({"enabled":enabled,"file":name,
				"shadow":luminance(image,camera.unproject_position(Vector3(.8,0,-.8))),
				"lit":luminance(image,camera.unproject_position(Vector3(2,0,-.8)))})
		var a:Dictionary=phases[0];var b:Dictionary=phases[1];var c:Dictionary=phases[2]
		var valid:bool=b.shadow>a.shadow+.08 and a.shadow<b.shadow*.65 and c.shadow<b.shadow*.65 and absf(a.shadow-c.shadow)<.04
		valid=valid and b.lit>.15 and absf(a.lit-b.lit)<.04 and absf(a.lit-c.lit)<.04
		cases.append({"kind":kind,"passed":valid,"phases":phases})
		passed=passed and valid
		light.queue_free()
		for frame in 8:await process_frame
	# Two simultaneous lights prove that the flag is per light, including its
	# SSBO array stride. A global switch could pass every single-light case.
	var red := OmniLight3D.new();red.light_color=Color.RED
	var blue := OmniLight3D.new();blue.light_color=Color.BLUE
	for light in [red,blue]:
		light.position=Vector3(-2,4,2);light.light_energy=40;light.omni_range=20;stage.add_child(light)
	var mixed_phases := []
	var mixed_valid := true
	for red_shadows in [true,false,true]:
		red.shadow_enabled=red_shadows;blue.shadow_enabled=not red_shadows
		if not await ready():push_error("Mixed-light fixture not ready");quit(3);return
		var image := root.get_texture().get_image()
		var name := "mixed-%d.png"%mixed_phases.size()
		if image.save_png(output.path_join(name))!=OK:quit(3);return
		var shadow := color_average(image,camera.unproject_position(Vector3(.8,0,-.8)))
		var lit := color_average(image,camera.unproject_position(Vector3(2,0,-.8)))
		var unblocked := shadow.z if red_shadows else shadow.x
		var blocked := shadow.x if red_shadows else shadow.z
		mixed_valid=mixed_valid and unblocked>.2 and blocked<.01 and lit.x>.1 and lit.z>.1
		mixed_phases.append({"red_shadows":red_shadows,"blue_shadows":not red_shadows,"shadow_rgb":[shadow.x,shadow.y,shadow.z],"lit_rgb":[lit.x,lit.y,lit.z],"file":name})
	cases.append({"kind":"mixed-omni","passed":mixed_valid,"phases":mixed_phases})
	passed=passed and mixed_valid
	FileAccess.open(output.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({"passed":passed,"query_shadows":query_shadows,"cases":cases,"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),"quality_accepted":false,"performance_accepted":false},"\t"))
	stage.queue_free()
	for frame in 8:await process_frame
	print("RT_LIGHT_SHADOW_TOGGLE_PASS" if passed else "RT_LIGHT_SHADOW_TOGGLE_FAIL")
	quit(0 if passed else 1)
