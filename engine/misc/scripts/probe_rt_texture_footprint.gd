extends SceneTree
## Colored mip levels distinguish texture filtering from denoiser smoothing.
## No denoiser, temporal AA, reconstruction, lighting noise or game assets.
var output := ""
var mode := "on"

func _initialize():
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):output=argument.trim_prefix("--output=")
		if argument.begins_with("--mode="):mode=argument.trim_prefix("--mode=")
	run.call_deferred()

func mip_texture() -> ImageTexture:
	var image:=Image.create(1024,1024,false,Image.FORMAT_RGBA8)
	image.fill(Color.RED);image.generate_mipmaps()
	var bytes:=image.get_data()
	for offset in range(image.get_mipmap_offset(1),bytes.size(),4):
		bytes[offset]=0;bytes[offset+1]=255;bytes[offset+2]=0;bytes[offset+3]=255
	return ImageTexture.create_from_image(Image.create_from_data(1024,1024,true,Image.FORMAT_RGBA8,bytes))

func run():
	if output.is_empty() or mode not in ["on","off","raster"] or DirAccess.dir_exists_absolute(output):
		push_error("Use a fresh output directory and on/off/raster mode");quit(2);return
	DirAccess.make_dir_recursive_absolute(output)
	root.size=Vector2i(320,240);root.use_taa=false
	root.scaling_3d_scale=1;root.scaling_3d_mode=Viewport.SCALING_3D_MODE_BILINEAR
	root.screen_space_aa=Viewport.SCREEN_SPACE_AA_DISABLED
	var scene:=Node3D.new();root.add_child(scene)
	var world:=WorldEnvironment.new();scene.add_child(world)
	world.environment=Environment.new()
	world.environment.background_mode=Environment.BG_COLOR
	world.environment.background_color=Color.BLACK
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_DISABLED
	world.environment.set("pathtracing_enabled",mode!="raster")
	world.environment.set("pathtracing_denoiser",0)
	world.environment.set("pathtracing_max_bounces",1)
	var camera:=Camera3D.new();scene.add_child(camera);camera.current=true
	camera.projection=Camera3D.PROJECTION_PERSPECTIVE;camera.fov=60;camera.near=.005
	camera.position=Vector3(0,5,0);camera.look_at(Vector3.ZERO,Vector3.FORWARD)
	var texture:=mip_texture()
	var box:=BoxMesh.new();box.size=Vector3(4,.1,4);box.add_uv2=true
	var compressed:=ArrayMesh.new()
	compressed.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,box.surface_get_arrays(0),[],{},Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES)
	var instance:=MeshInstance3D.new();instance.mesh=box;scene.add_child(instance)
	var cases:=[
		{"name":"uv-far"},
		{"name":"uv-near","near":true},
		{"name":"uv-nearest","nearest":true},
		{"name":"uv-mirrored","scale":Vector3(-3,.5,1)},
		{"name":"uv-compressed","compressed":true},
		{"name":"triplanar-local","triplanar":true},
		{"name":"triplanar-world","triplanar":true,"world":true},
		{"name":"triplanar-near","triplanar":true,"near":true},
		{"name":"triplanar-transformed","triplanar":true,"transformed":true},
		{"name":"triplanar-compressed","triplanar":true,"compressed":true},
		{"name":"uv-perspective","perspective":true},
		{"name":"triplanar-oblique","triplanar":true,"perspective":true},
		{"name":"detail-uv1","detail":true},
		{"name":"detail-uv2","detail":true,"uv2":true},
		{"name":"detail-triplanar-uv1","detail":true,"triplanar":true},
		{"name":"detail-triplanar-uv2","detail":true,"triplanar":true,"uv2":true}
	]
	var rows:=[];var all_passed:=true
	for test in cases:
		instance.mesh=compressed if test.get("compressed",false) else box
		instance.scale=Vector3(1.7,.7,.8) if test.get("transformed",false) else Vector3.ONE
		instance.rotation.y=.37 if test.get("transformed",false) else 0.0
		var material:=StandardMaterial3D.new()
		material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		material.albedo_texture=texture
		material.texture_filter=BaseMaterial3D.TEXTURE_FILTER_NEAREST if test.get("nearest",false) else BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		material.uv1_triplanar=test.get("triplanar",false)
		material.uv1_world_triplanar=test.get("world",false)
		material.uv1_scale=test.get("scale",Vector3.ONE)
		if test.get("detail",false):
			material.detail_enabled=true;material.detail_albedo=texture
			material.detail_uv_layer=BaseMaterial3D.DETAIL_UV_2 if test.get("uv2",false) else BaseMaterial3D.DETAIL_UV_1
			material.uv2_triplanar=test.get("triplanar",false)
		instance.material_override=material
		camera.position=Vector3(2,5,3) if test.get("perspective",false) else Vector3(0,5,0)
		if test.get("near",false):camera.position=Vector3(0,.12,0)
		camera.look_at(Vector3.ZERO,Vector3.FORWARD)
		var started:=Time.get_ticks_msec();var stable:=0
		while Time.get_ticks_msec()-started<120000:
			await process_frame;await RenderingServer.frame_post_draw
			var ready:=mode=="raster" or RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_SCENE_READY)>0
			var pending:=RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_PENDING_MATERIALS)
			stable=stable+1 if ready and pending==0 else 0
			if stable>=12:break
		if stable<12:push_error("Texture footprint fixture not ready");quit(3);return
		var capture:=root.get_texture().get_image()
		var red:=0.0;var green:=0.0
		for y in range(108,132):
			for x in range(148,172):
				var pixel:=capture.get_pixel(x,y);red+=pixel.r/576.;green+=pixel.g/576.
		var filtered:bool=mode!="off" and not test.get("near",false) and not test.get("nearest",false)
		var passed:=green>.75 and red<.1 if filtered else red>.75 and green<.1
		rows.append({"case":test.name,"expected_filtered":filtered,"red":red,"green":green,"passed":passed})
		all_passed=all_passed and passed
		capture.save_png(output.path_join(test.name+".png"))
		print("RT_TEXTURE_FOOTPRINT ",test.name," passed=",passed," red=",red," green=",green)
	FileAccess.open(output.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({"passed":all_passed,"mode":mode,"cases":rows,"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),"denoiser":false,"performance_accepted":false,"secondary_rays_accepted":false},"\t"))
	scene.queue_free()
	for frame in 8:await process_frame
	quit(0 if all_passed else 4)
