extends SceneTree
## Generic opt-in transport fixture. The companion verifier must inspect the
## actual submitted buffers; a matching display image alone is insufficient.

class Capture extends CompositorEffect:
	var mutex := Mutex.new()
	var result := {}
	var error := ""
	var omit_directional := false
	var injected := false

	func _init() -> void:
		effect_callback_type = EFFECT_CALLBACK_TYPE_POST_OPAQUE

	func snapshot() -> Dictionary:
		mutex.lock()
		var value := {"result":result.duplicate(),"error":error}
		mutex.unlock()
		return value

	func _render_callback(_type: int,data: RenderData) -> void:
		mutex.lock()
		if not result.is_empty() or not error.is_empty():
			mutex.unlock();return
		var buffers: RenderSceneBuffersRD = data.get_render_scene_buffers()
		var scene_data: RenderSceneDataRD = data.get_render_scene_data()
		var state: Dictionary = buffers.get_meta("rt_light_grid_capture",{})
		if state.is_empty(): mutex.unlock();return
		var frame := int(state.frame_index)
		var rd := RenderingServer.get_rendering_device()
		if omit_directional and frame == 191:
			var lights := rd.buffer_get_data(state.light_buffer)
			var words := rd.buffer_get_data(state.grid_buffer)
			var index := -1
			for light in int(state.light_count):
				if lights.decode_u32(light*112+12)==1: index=light;break
			if index<0 or not state.grid_enabled:
				error="Negative control requires an indexed directional light"
			else:
				var mask := 0xffffffff ^ (1 << (index%32))
				for base in range(8,words.size()/4,2):
					if base==10: continue # Header flags, not a mask.
					var offset := (base+index/32)*4
					words.encode_u32(offset,words.decode_u32(offset)&mask)
				if rd.buffer_update(state.grid_buffer,0,words.size(),words)!=OK:
					error="Cannot submit negative control"
				injected=true
		if frame==192 and error.is_empty():
			if omit_directional and not injected: error="Negative control was not submitted"
			elif not buffers.has_texture("forward_clustered","raytracing"): error="Missing raw transport texture"
			else:
				result={"frame":frame,"lights":int(state.light_count),"stride":int(state.light_stride),
					"grid_enabled":bool(state.grid_enabled),"grid_words":int(state.grid_word_count),"size":buffers.get_internal_size(),
					"jitter":scene_data.get_taa_jitter(),
					"raw":rd.texture_get_data(buffers.get_texture("forward_clustered","raytracing"),0),
					"light_bytes":rd.buffer_get_data(state.light_buffer),
					"grid_bytes":rd.buffer_get_data(state.grid_buffer),"negative_control":injected}
				var reconstruction:Dictionary=buffers.get_meta("dlss_diagnostics",{})
				if reconstruction.get("backend")!="DLSS" or not reconstruction.get("viewport_renderer",false) or not reconstruction.get("evaluation_succeeded",false) or int(reconstruction.get("frames",0))<60:
					error="Missing successful native DLSS evaluations"
				else:
					var input_size:Vector2i=reconstruction.get("size",Vector2i.ZERO)
					var output_size:Vector2i=reconstruction.get("output_size",Vector2i.ZERO)
					result["reconstruction"]={"backend":reconstruction.backend,"frames":int(reconstruction.frames),
						"viewport_renderer":true,"evaluation_succeeded":true,"size":[input_size.x,input_size.y],"output_size":[output_size.x,output_size.y]}
		elif frame>192 and result.is_empty() and error.is_empty(): error="Missed requested transport frame"
		mutex.unlock()

var output := ""
var zero_indirect := false

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg=="--zero-indirect":zero_indirect=true
		if arg.begins_with("--output="): output=arg.trim_prefix("--output=")
	call_deferred("run")

func mesh(parent: Node3D,shape: Mesh,position: Vector3,color: Color,metallic: float,roughness: float) -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color=color;material.metallic=metallic;material.roughness=roughness
	var node := MeshInstance3D.new();node.mesh=shape;node.position=position;node.material_override=material
	parent.add_child(node)

func scene(viewport: SubViewport,capture: Capture) -> void:
	var stage := Node3D.new();viewport.add_child(stage)
	var world := WorldEnvironment.new();world.environment=Environment.new();stage.add_child(world)
	world.environment.background_mode=Environment.BG_COLOR
	world.environment.background_color=Color(0.025,0.025,0.025)
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_DISABLED
	world.environment.set("pathtracing_enabled",true)
	world.environment.set("pathtracing_denoiser",1)
	world.environment.set("pathtracing_samples_per_pixel",1)
	world.environment.set("pathtracing_max_bounces",3)
	world.compositor=Compositor.new();world.compositor.compositor_effects=[capture]
	var plane := PlaneMesh.new();plane.size=Vector2(24,24)
	mesh(stage,plane,Vector3.ZERO,Color(0.45,0.45,0.45),0.0,0.8)
	for i in 3:
		var sphere := SphereMesh.new();sphere.radius=0.8;sphere.height=1.6
		mesh(stage,sphere,Vector3((i-1)*2.5,0.8,0),Color(0.6,0.55,0.45),float(i>0),0.08+i*0.25)
	for i in 63:
		var light: Light3D
		match i%3:
			0:
				var omni := OmniLight3D.new();omni.omni_range=2.0+(i%5)*0.5;light=omni
			1:
				var spot := SpotLight3D.new();spot.spot_range=3.0+(i%5)*0.5;spot.spot_angle=55.0;light=spot
			2:
				var area := AreaLight3D.new();area.area_range=3.0+(i%5)*0.5;area.area_size=Vector2(0.4,0.25);light=area
		stage.add_child(light)
		light.position=Vector3((i%9-4)*2.1,2.0+float(i)*0.007,(i/9-3)*2.0)
		if i%3!=0: light.look_at(light.position+Vector3.DOWN,Vector3.FORWARD)
		light.light_energy=5.0+float(i)*0.03;light.light_color=Color.from_hsv(float(i)/63.0,0.3,1.0)
		light.light_indirect_energy=0.0 if zero_indirect and i%2==0 else 0.6;light.shadow_enabled=true
	var directional := DirectionalLight3D.new();stage.add_child(directional)
	directional.rotation_degrees=Vector3(-55,-25,0);directional.light_energy=0.35;directional.shadow_enabled=true
	var camera := Camera3D.new();stage.add_child(camera);camera.current=true
	camera.position=Vector3(4,6,10);camera.look_at(Vector3(0,0.7,0))

func run() -> void:
	if output.is_empty() or DirAccess.dir_exists_absolute(output): push_error("Choose a fresh output directory");quit(2);return
	if DirAccess.make_dir_recursive_absolute(output)!=OK: quit(2);return
	var rows := []
	for label in ["warmup","enumeration","indexed","missing_directional"]:
		OS.set_environment("GODOT_RT_LIGHT_GRID","0" if label in ["warmup","enumeration"] else "1")
		var viewport := SubViewport.new();viewport.size=Vector2i(640,360);viewport.own_world_3d=true
		viewport.render_target_update_mode=SubViewport.UPDATE_DISABLED
		viewport.scaling_3d_mode=Viewport.SCALING_3D_MODE_DLSS;viewport.scaling_3d_scale=0.5
		viewport.msaa_3d=Viewport.MSAA_DISABLED;viewport.use_taa=false
		root.add_child(viewport)
		var capture := Capture.new();capture.omit_directional=label=="missing_directional"
		scene(viewport,capture)
		# Jitter uses the renderer's global frame, while path RNG uses a viewport
		# counter. Start fresh viewports at the same 32-phase jitter position.
		while Engine.get_frames_drawn()%32!=0: await process_frame
		viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
		var deadline := Time.get_ticks_msec()+180000
		var state := capture.snapshot()
		while state.result.is_empty() and state.error.is_empty() and Time.get_ticks_msec()<deadline:
			await process_frame;state=capture.snapshot()
		if not state.error.is_empty() or state.result.is_empty():
			push_error("Transport capture failed: %s %s" % [label,state.error]);quit(3);return
		var result: Dictionary=state.result
		if label=="warmup":
			capture.enabled=false;viewport.queue_free();await process_frame;await process_frame
			continue
		for key in ["raw","light_bytes","grid_bytes"]:
			FileAccess.open(output.path_join(label+"-"+key+".bin"),FileAccess.WRITE).store_buffer(result[key])
			result.erase(key)
		var dimensions: Vector2i=result["size"]
		result["size"]=[dimensions.x,dimensions.y]
		result["jitter"]=[result.jitter.x,result.jitter.y]
		result["case"]=label;rows.append(result)
		capture.enabled=false;viewport.render_target_update_mode=SubViewport.UPDATE_DISABLED
		viewport.queue_free();await process_frame;await process_frame
	FileAccess.open(output.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({"captured":true,"qualified":false,"zero_indirect":zero_indirect,"cases":rows},"\t"))
	print("RT_LIGHT_GRID_TRANSPORT_CAPTURED")
	quit()
