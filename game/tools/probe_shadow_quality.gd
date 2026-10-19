extends SceneTree
## Isolate physical light size from reconstruction blur. Not an FPS test.
const Preparation=preload("res://scripts/core/resource_preparation.gd")
const DenoiserObserver=preload("res://scripts/debug/reconstruction_observer.gd")
var mode:="dlss"
var prefix:="shadow-quality"
var output_size:=Vector2i(640,360)

func _initialize():run.call_deferred()

func object(parent: Node3D,shape: Mesh,position: Vector3,color: Color):
	var node:=MeshInstance3D.new();node.mesh=shape;node.position=position
	var material:=StandardMaterial3D.new();material.albedo_color=color;material.roughness=.8
	node.material_override=material;parent.add_child(node)

func run():
	create_timer(300).timeout.connect(func():push_error("SHADOW_QUALITY_TIMEOUT");quit(8))
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--mode="):mode=argument.get_slice("=",1)
		if argument.begins_with("--prefix="):prefix=argument.get_slice("=",1)
		if argument.begins_with("--width="):output_size.x=int(argument.get_slice("=",1))
		if argument.begins_with("--height="):output_size.y=int(argument.get_slice("=",1))
	if mode not in ["reference","dlss","dlss-half"]:quit(2);return
	if mode!="reference" and OS.get_environment("GODOT_DLSS_DIAGNOSTICS")!="1":
		push_error("DLSS shadow qualification requires native evaluation diagnostics");quit(2);return
	var directory:="res://reports/performance/"+prefix+"-"+mode
	if DirAccess.dir_exists_absolute(directory):push_error("Use a fresh shadow capture prefix");quit(2);return
	DirAccess.make_dir_recursive_absolute(directory)
	root.size=output_size
	var results:=[]
	for kind in ["point","area-small","area-large","area-back"]:
		var stage:=Node3D.new();root.add_child(stage)
		var world:=WorldEnvironment.new();world.environment=Environment.new();stage.add_child(world)
		world.environment.background_mode=Environment.BG_COLOR
		world.environment.background_color=Color(.01,.01,.01)
		world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
		world.environment.ambient_light_color=Color.WHITE;world.environment.ambient_light_energy=.03
		world.environment.tonemap_mode=Environment.TONE_MAPPER_FILMIC
		var observer=null
		var floor_mesh:=PlaneMesh.new();floor_mesh.size=Vector2(16,16)
		object(stage,floor_mesh,Vector3.ZERO,Color(.4,.4,.4))
		object(stage,BoxMesh.new(),Vector3(0,.5,0),Color(.25,.25,.25))
		var camera:=Camera3D.new();stage.add_child(camera);camera.current=true
		camera.position=Vector3(3,4,-5);camera.look_at(Vector3(.4,0,-.6))
		var light:Light3D
		if kind=="point":
			var point:=OmniLight3D.new();point.omni_range=20;light=point
		else:
			var area:=AreaLight3D.new();area.area_range=20
			area.area_size=Vector2(.15,.15) if kind=="area-small" else Vector2(2,2)
			light=area
		light.position=Vector3(-2,4,2);light.light_energy=40;light.shadow_enabled=true
		stage.add_child(light)
		if kind!="point":light.look_at(Vector3.ZERO)
		if kind=="area-back":light.rotate_object_local(Vector3.UP,PI)
		var prefs:=Preferences.new("user://shadow-quality-unused.cfg")
		prefs.values.ray_tracing=true;prefs.values.fixture_lighting=true;prefs.values.antialiasing=0
		prefs.apply_rendering(stage)
		if not world.environment.get("pathtracing_enabled"):
			push_error("Hardware path tracing unavailable");quit(3);return
		root.scaling_3d_scale=.5 if mode=="dlss-half" else 1.;root.use_taa=false
		root.scaling_3d_mode=Viewport.SCALING_3D_MODE_DLSS if mode.begins_with("dlss") else Viewport.SCALING_3D_MODE_BILINEAR
		world.environment.set("pathtracing_denoiser",1 if mode.begins_with("dlss") else 0)
		world.environment.set("pathtracing_samples_per_pixel",1)
		if mode!="reference":
			observer=DenoiserObserver.new()
			var compositor:=Compositor.new();compositor.compositor_effects=[observer]
			world.compositor=compositor
		var ready:Dictionary=await Preparation.wait_for_rendering(self,root,true)
		if not ready.ready:push_error(str(ready));quit(4);return
		for frame in 120:await RenderingServer.frame_post_draw
		# A new environment may replace the viewport's native DLSS context.
		# Compare consecutive evaluations after settling, not a counter retained
		# from the preceding scene's context.
		var initial_denoiser:Dictionary=observer.stats() if observer else {}
		for frame in 4:await RenderingServer.frame_post_draw
		if mode=="reference":
			# Compile/warm the scene cheaply. A raw reference needs no denoiser
			# history: raise sample count only for its final converged captures.
			world.environment.set("pathtracing_samples_per_pixel",128)
			await process_frame
			ready=await Preparation.wait_for_rendering(self,root,true)
			if not ready.ready:push_error(str(ready));quit(4);return
			for frame in 3:await RenderingServer.frame_post_draw
		var filename:String=kind+".png"
		if root.get_texture().get_image().save_png(directory.path_join(filename))!=OK:quit(5);return
		var final_denoiser:Dictionary=observer.stats() if observer else {}
		if observer and (not String(final_denoiser.error).is_empty() or not final_denoiser.adapter.get("evaluation_succeeded",false) or int(final_denoiser.adapter.get("frames",0))<=int(initial_denoiser.adapter.get("frames",0))):
			FileAccess.open(directory.path_join(kind+"-evaluation-failure.json"),FileAccess.WRITE).store_string(JSON.stringify({"before":initial_denoiser,"after":final_denoiser},"\t"))
			push_error("Shadow capture lacks advancing native DLSS evaluation");quit(6);return
		var profile:=[]
		for index in 121:
			var point:=Vector3(lerpf(.6,2.5,float(index)/120),.001,-.8)
			var pixel:=camera.unproject_position(point);profile.append([pixel.x,pixel.y])
		results.append({"light":kind,"image":filename,"shadow_profile_pixels":profile,
			"denoiser_before":initial_denoiser,"denoiser_after":final_denoiser,
			"area_size":str(light.area_size) if light is AreaLight3D else "point",
			"area_normalize_energy":light.area_normalize_energy if light is AreaLight3D else false})
		print("SHADOW_QUALITY_CASE ",mode," ",kind)
		if observer:
			observer.release()
			while not observer.stats().released:await process_frame
			world.compositor=null
			observer=null
		stage.queue_free()
		for frame in 6:await process_frame
	FileAccess.open(directory.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({
		"mode":mode,"samples_per_pixel":128 if mode=="reference" else 1,"native_output":[output_size.x,output_size.y],
		"capture_revision":2,"observer_sha256":FileAccess.get_sha256("res://scripts/debug/reconstruction_observer.gd"),
		"internal_scale":.5 if mode=="dlss-half" else 1.,
		"cases":results,"capture_passed":true,"visual_quality_acceptance":false,"performance_acceptance":false},"\t"))
	print("SHADOW_QUALITY_CAPTURE_PASS ",mode)
	quit()
