extends SceneTree
## Same-viewport SR/RR switching. This is not a quality or performance benchmark.
var output := ""
var sr_preset := "default"
var rr_preset := "default"
var output_size := Vector2i(640,360)

class Observer extends CompositorEffect:
	var mutex := Mutex.new()
	var state := {}
	func _init() -> void:
		effect_callback_type=EFFECT_CALLBACK_TYPE_POST_TRANSPARENT
		access_resolved_color=true
	func _render_callback(_type:int,data:RenderData) -> void:
		mutex.lock()
		state=data.get_render_scene_buffers().get_meta("dlss_diagnostics",{}).duplicate(true)
		mutex.unlock()
	func snapshot() -> Dictionary:
		mutex.lock();var result:=state.duplicate(true);mutex.unlock()
		for key in ["size","output_size"]:
			if result.has(key):
				var value:Vector2i=result[key];result[key]=[value.x,value.y]
		return result

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="):output=arg.trim_prefix("--output=")
		if arg.begins_with("--sr-preset="):sr_preset=arg.trim_prefix("--sr-preset=")
		if arg.begins_with("--rr-preset="):rr_preset=arg.trim_prefix("--rr-preset=")
		if arg.begins_with("--resolution="):
			var dimensions:=arg.trim_prefix("--resolution=").split("x")
			if dimensions.size()!=2:quit(2);return
			output_size=Vector2i(int(dimensions[0]),int(dimensions[1]))
	run.call_deferred()

func frames(count:int) -> void:
	for i in count:await process_frame;await RenderingServer.frame_post_draw

func run() -> void:
	if output.is_empty() or DirAccess.dir_exists_absolute(output):quit(2);return
	if sr_preset not in ["default","K","L","M"] or rr_preset not in ["default","D","E"]:quit(2);return
	if DirAccess.make_dir_recursive_absolute(output)!=OK:quit(2);return
	if sr_preset != "default":
		Streamline.set_parameter(Streamline.STREAMLINE_PARAM_DLSS_PRESET,sr_preset)
	print("DLSS_LIFECYCLE_SR_PRESET ",sr_preset)
	if rr_preset != "default":
		Streamline.set_parameter(Streamline.STREAMLINE_PARAM_DLSS_RR_PRESET,rr_preset)
	print("DLSS_LIFECYCLE_RR_PRESET ",rr_preset)
	root.borderless=true;root.size=output_size
	root.scaling_3d_mode=Viewport.SCALING_3D_MODE_DLSS;root.scaling_3d_scale=.5
	root.msaa_3d=Viewport.MSAA_DISABLED;root.use_taa=false
	var viewport_identity:=str(root.get_viewport_rid())
	var stage:=Node3D.new();root.add_child(stage)
	var world:=WorldEnvironment.new();world.environment=Environment.new();stage.add_child(world)
	world.environment.background_mode=Environment.BG_COLOR;world.environment.background_color=Color(.02,.02,.02)
	world.environment.tonemap_mode=Environment.TONE_MAPPER_LINEAR
	world.environment.set("pathtracing_denoiser",1);world.environment.set("pathtracing_max_bounces",3)
	var observer:=Observer.new();world.compositor=Compositor.new();world.compositor.compositor_effects=[observer]
	var camera:=Camera3D.new();stage.add_child(camera);camera.position.z=5;camera.current=true
	var target:=MeshInstance3D.new();var shape:=QuadMesh.new();shape.size=Vector2(2,2);target.mesh=shape
	var material:=StandardMaterial3D.new();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	target.material_override=material;stage.add_child(target)
	var rows:=[]
	for phase in [{"name":"sr-first","rr":false,"color":Color(.8,.05,.05)},
			{"name":"rr-first","rr":true,"color":Color(.05,.8,.05)},
			{"name":"sr-return","rr":false,"color":Color(.05,.05,.8)},
			{"name":"rr-return","rr":true,"color":Color(.8,.65,.05)}]:
		print("DLSS_LIFECYCLE_PHASE ",phase.name)
		world.environment.set("pathtracing_enabled",phase.rr);material.albedo_color=phase.color
		await frames(150)
		var deadline:=Time.get_ticks_msec()+90000
		var stats:=observer.snapshot()
		while phase.rr and (stats.get("frames",0)<64 or not stats.get("evaluation_succeeded",false)):
			if Time.get_ticks_msec()>deadline:push_error("RR did not become ready: "+phase.name);quit(3);return
			await frames(1);stats=observer.snapshot()
		if not phase.rr and not stats.is_empty():push_error("Stale RR diagnostics after SR switch");quit(3);return
		if phase.rr and (stats.get("size")!=[output_size.x/2,output_size.y/2] or stats.get("output_size")!=[output_size.x,output_size.y]):
			push_error("RR dimensions changed");quit(3);return
		if str(root.get_viewport_rid())!=viewport_identity:push_error("Viewport was replaced");quit(3);return
		var image:=root.get_texture().get_image();var color:=Vector3.ZERO
		if image.get_size()!=output_size:push_error("Unexpected output dimensions");quit(3);return
		for y in range(output_size.y/2-4,output_size.y/2+5):
			for x in range(output_size.x/2-4,output_size.x/2+5):
				var pixel:=image.get_pixel(x,y);color+=Vector3(pixel.r,pixel.g,pixel.b)
		color/=81.0
		var expected:Color=phase.color
		if maxf(absf(color.x-expected.r),maxf(absf(color.y-expected.g),absf(color.z-expected.b)))>.12:
			push_error("Missing fresh phase color: "+phase.name+" "+str(color));quit(3);return
		image.save_png(output.path_join(phase.name+".png"))
		rows.append({"phase":phase.name,"rr":phase.rr,"mean_rgb":[color.x,color.y,color.z],"native":stats,"viewport":viewport_identity})
	FileAccess.open(output.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({"passed":true,"sr_preset":sr_preset,"rr_preset":rr_preset,"output_size":[output_size.x,output_size.y],"rows":rows},"\t"))
	observer.enabled=false;world.compositor=null;stage.queue_free();await frames(3);observer=null
	print("DLSS_FEATURE_LIFECYCLE_PASS phases=4");quit()
