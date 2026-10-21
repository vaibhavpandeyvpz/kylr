extends SceneTree
const Preparation=preload("res://scripts/core/resource_preparation.gd")

func _initialize():run.call_deferred()

func run():
	create_timer(150).timeout.connect(func():push_error("ARMOR_OVERLAY_TIMEOUT");quit(8))
	var mode:="dlss";var prefix:="armor-overlay";var variant:="authored"
	var smaa:="--smaa" in OS.get_cmdline_user_args()
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--mode="):mode=argument.get_slice("=",1)
		if argument.begins_with("--prefix="):prefix=argument.get_slice("=",1)
		if argument.begins_with("--variant="):variant=argument.get_slice("=",1)
	if mode not in ["raster","dlss"]:quit(2);return
	if variant not in ["authored","no-depth","offset-10mm","double-sided"]:quit(2);return
	var requested:=Preferences.DENOISER_DLSS
	if mode!="raster" and not Preferences.ray_tracing_unavailable_reason(requested).is_empty():
		push_error(Preferences.ray_tracing_unavailable_reason(requested));quit(2);return
	var directory:="res://reports/performance/"+prefix+"-"+mode
	if DirAccess.dir_exists_absolute(directory):push_error("Use a fresh overlay report prefix");quit(2);return
	DirAccess.make_dir_recursive_absolute(directory)
	root.size=Vector2i(640,720)
	var stage:=Node3D.new();root.add_child(stage)
	var world:=ArenaLighting.install(stage,true)
	var body:=Assets.model("characters","tensor");stage.add_child(body)
	Assets.paint(body,Color(.65,.05,.04),Color(.3,.3,.3))
	var floor_node:=MeshInstance3D.new();var plane:=PlaneMesh.new();plane.size=Vector2(8,8)
	floor_node.mesh=plane;stage.add_child(floor_node)
	var camera:=Camera3D.new();stage.add_child(camera);camera.current=true
	camera.position=Vector3(1.5,1.3,2.5);camera.look_at(Vector3(0,.85,0))
	var prefs:=Preferences.new("user://armor-overlay-probe-unused.cfg")
	prefs.values.rt_denoiser=Preferences.DENOISER_DLSS
	prefs.values.ray_tracing=mode!="raster";prefs.values.fixture_lighting=true;prefs.values.antialiasing=0
	prefs.apply_rendering(stage)
	# Compare at native size so reconstruction resolution does not hide depth defects.
	root.scaling_3d_scale=1.;root.use_taa=false
	root.screen_space_aa=Viewport.SCREEN_SPACE_AA_SMAA if smaa else Viewport.SCREEN_SPACE_AA_DISABLED
	var ready:Dictionary=await Preparation.wait_for_rendering(self,root,mode!="raster")
	if not ready.ready:push_error(str(ready));quit(3);return
	for frame in 64:await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(directory.path_join("base.png"))
	var flash:=ShaderMaterial.new()
	var authored_shader:=preload("res://shaders/combat/energy_surface.gdshader")
	var code:=authored_shader.code
	match variant:
		"no-depth":code=code.replace("depth_draw_never, cull_back;","depth_draw_never, depth_test_disabled, cull_back;")
		"offset-10mm":code=code.replace("NORMAL*surface_offset","NORMAL*0.01")
		"double-sided":code=code.replace("cull_back;","cull_disabled;")
	if variant=="authored":flash.shader=authored_shader
	else:
		# Deliberately invalid visibility variants are diagnostic controls only.
		# Never mutate the shared production shader or qualify these for release.
		if code==authored_shader.code:push_error("Diagnostic variant did not change shader");quit(4);return
		flash.shader=Shader.new();flash.shader.code=code
	flash.set_shader_parameter("hit_strength",.8)
	for mesh in body.find_children("*","MeshInstance3D",true,false):mesh.material_overlay=flash
	for frame in 64:await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(directory.path_join("flash.png"))
	# An opaque foreground object must continue to hide the overlay.
	var cover:=MeshInstance3D.new();cover.mesh=BoxMesh.new();cover.position=Vector3(.3,.8,1)
	stage.add_child(cover)
	for frame in 64:await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(directory.path_join("occluded.png"))
	FileAccess.open(directory.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({
		"mode":mode,"smaa":smaa,"screen_space_aa":root.screen_space_aa,"variant":variant,"diagnostic_variant":variant!="authored","effective_shader_sha256":code.sha256_text(),"native_output":[640,720],"strength":.8,"capture_passed":true,
		"separate_rendering_thread":not RenderingServer.is_on_render_thread(),
		"performance_acceptance":false,"visual_quality_acceptance":false},"\t"))
	print("ARMOR_OVERLAY_CAPTURE_PASS ",mode)
	stage.queue_free()
	for frame in 6:await process_frame
	quit()
