extends SceneTree
## Deterministic raster reference for finite-range and shadowed area lighting.
## Compare captures from reference/candidate binaries; this is not an FPS test.

var output := ""
var viewport: SubViewport
var lights: Array[AreaLight3D] = []

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):
			output=argument.trim_prefix("--output=")
	if output.is_empty() or DirAccess.dir_exists_absolute(output):
		push_error("Pass a fresh absolute --output directory")
		quit(1)
		return
	run.call_deferred()

func settle() -> void:
	for frame in 120:
		await process_frame
	await RenderingServer.frame_post_draw

func save_capture(name: String) -> Dictionary:
	await settle()
	var image := viewport.get_texture().get_image()
	var original_format := image.get_format()
	image.save_png(output.path_join(name+".png"))
	image.convert(Image.FORMAT_RGBAF)
	var file := FileAccess.open(output.path_join(name+".rgba32f"),FileAccess.WRITE)
	file.store_buffer(image.get_data())
	return {"name":name,"width":image.get_width(),"height":image.get_height(),"source_format":original_format,"bytes":image.get_data().size()}

func run() -> void:
	if DirAccess.make_dir_recursive_absolute(output)!=OK:
		quit(1)
		return
	RenderingServer.positional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_HARD)
	RenderingServer.directional_soft_shadow_filter_set_quality(RenderingServer.SHADOW_QUALITY_HARD)
	viewport=SubViewport.new()
	viewport.size=Vector2i(640,480)
	viewport.use_hdr_2d=true
	viewport.own_world_3d=true
	viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var world := WorldEnvironment.new()
	world.environment=Environment.new()
	world.environment.background_mode=Environment.BG_COLOR
	world.environment.background_color=Color(0.02,0.02,0.02)
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_energy=0.04
	world.environment.reflected_light_source=Environment.REFLECTION_SOURCE_DISABLED
	world.environment.tonemap_mode=Environment.TONE_MAPPER_LINEAR
	viewport.add_child(world)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	camera.position=Vector3(0,8,10)
	camera.look_at(Vector3.ZERO)
	camera.current=true
	for index in 3:
		var light := AreaLight3D.new()
		viewport.add_child(light)
		light.position=Vector3((index-1)*2.0,4,index-1)
		light.rotation_degrees.x=-90
		light.area_size=Vector2(2,2)
		light.area_range=5
		light.light_energy=1.5
		light.light_color=[Color(1,0.7,0.5),Color(0.5,0.7,1),Color(0.7,1,0.5)][index]
		light.shadow_enabled=true
		lights.append(light)
	var blocker := MeshInstance3D.new()
	blocker.mesh=BoxMesh.new()
	blocker.mesh.size=Vector3(2,0.3,2)
	viewport.add_child(blocker)
	blocker.position=Vector3(0,2,0)
	var receivers: Array[MeshInstance3D] = []
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size=Vector2(14,14)
	floor_mesh.mesh=plane
	viewport.add_child(floor_mesh)
	receivers.append(floor_mesh)
	for point in [Vector3(0,0.4,-2),Vector3(0,0.4,0),Vector3(3.8,0.4,3.8)]:
		var sphere := MeshInstance3D.new()
		sphere.mesh=SphereMesh.new()
		sphere.mesh.radius=0.4
		sphere.mesh.height=0.8
		viewport.add_child(sphere)
		sphere.position=point
		receivers.append(sphere)
	var cases := {
		"diffuse":"void fragment(){ ALBEDO=vec3(0.6,0.4,0.3); ROUGHNESS=0.7; }",
		"metal":"void fragment(){ ALBEDO=vec3(0.8); METALLIC=1.0; ROUGHNESS=0.2; }",
		"clearcoat":"void fragment(){ ALBEDO=vec3(0.5); ROUGHNESS=0.5; CLEARCOAT=0.8; CLEARCOAT_ROUGHNESS=0.5; }",
		"transmission":"void fragment(){ ALBEDO=vec3(0.6,0.3,0.2); SSS_STRENGTH=0.4; SSS_TRANSMITTANCE_COLOR=vec4(0.7,0.3,0.2,0.5); SSS_TRANSMITTANCE_DEPTH=0.5; SSS_TRANSMITTANCE_BOOST=1.0; }",
		"rim_backlight":"void fragment(){ ALBEDO=vec3(0.4); RIM=0.5; BACKLIGHT=vec3(0.3); }",
		"custom_area":"void fragment(){ ALBEDO=vec3(0.4); } void light(){ if(LIGHT_IS_AREA){ DIFFUSE_LIGHT+=vec3(0.08,0.03,0.02); } }",
		"transparent":"void fragment(){ ALBEDO=vec3(0.3,0.5,0.7); ALPHA=0.5; ROUGHNESS=0.4; }",
	}
	var captures: Array = []
	for name in cases:
		var material := ShaderMaterial.new()
		material.shader=Shader.new()
		material.shader.code="shader_type spatial; "+cases[name]
		for receiver in receivers:
			receiver.material_override=material
		captures.append(await save_capture(name))
	for light in lights:
		light.visible=false
	captures.append(await save_capture("lights_disabled_control"))
	FileAccess.open(output.path_join("captures.json"),FileAccess.WRITE).store_string(JSON.stringify({"captures":captures,"performance_acceptance":false},"\t"))
	viewport.queue_free()
	await process_frame
	print("AREA_LIGHT_REFERENCE_COMPLETE ",captures.size())
	quit()
