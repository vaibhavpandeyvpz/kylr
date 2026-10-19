extends SceneTree
## A flat, high-contrast silhouette makes vacated pixels independently testable.
## This is a diagnostic, not a full-scene or performance qualification.
const TRAIL_LIMIT := 0.05
const STEPS := 32
var output := ""
var backend := "raster"
var rr_preset := "default"
var sr_preset := "default"
var super_resolution := false
var scale := 0.5
var inject_ghost := false
var projection := "perspective"
var sharpening := -1.0
var capture_inputs := false
var movement_direction := 1.0
var ghost_writes_depth := false
var output_size := Vector2i(640,360)
var camera: Camera3D
var stage: Node3D
var observer: Observer

class Observer extends CompositorEffect:
	var super_resolution := false
	var mutex := Mutex.new()
	var state := {}
	var request := []
	var pending_readback := {}
	var observations := []
	var probe_shader:RID
	var probe_pipeline:RID
	var probe_sampler:RID
	var probe_buffer:RID
	func release() -> void:
		enabled=false;RenderingServer.call_on_render_thread(_release)
	func _release() -> void:
		var rd:=RenderingServer.get_rendering_device()
		for rid in [probe_pipeline,probe_shader,probe_sampler,probe_buffer]:
			if rid.is_valid():rd.free_rid(rid)
	func arm(points: Array) -> void:
		mutex.lock();request=points.duplicate(true);observations.clear();mutex.unlock()
	func input_samples() -> Array:
		mutex.lock();var result:=observations.duplicate(true);mutex.unlock();return result
	func _init() -> void:
		effect_callback_type=EFFECT_CALLBACK_TYPE_POST_TRANSPARENT
		access_resolved_color=true
	func _render_callback(_type: int,data: RenderData) -> void:
		var buffers:RenderSceneBuffersRD=data.get_render_scene_buffers()
		mutex.lock();state=buffers.get_meta("dlss_sr_diagnostics" if super_resolution else "dlss_diagnostics",{}).duplicate(true)
		var points:=request.duplicate(true);request.clear();mutex.unlock()
		if points.is_empty():return
		var rd:=RenderingServer.get_rendering_device()
		var size:=buffers.get_internal_size()
		var depth_texture:=buffers.get_depth_texture() if super_resolution else buffers.get_texture("forward_clustered","rt_depth")
		var velocity_texture:=buffers.get_velocity_texture()
		var depth_format:=rd.texture_get_format(depth_texture).format
		var valid_depth_formats:=[RenderingDevice.DATA_FORMAT_R32_SFLOAT,RenderingDevice.DATA_FORMAT_D16_UNORM,RenderingDevice.DATA_FORMAT_X8_D24_UNORM_PACK32,RenderingDevice.DATA_FORMAT_D32_SFLOAT,RenderingDevice.DATA_FORMAT_D24_UNORM_S8_UINT,RenderingDevice.DATA_FORMAT_D32_SFLOAT_S8_UINT]
		if depth_format not in valid_depth_formats or rd.texture_get_format(velocity_texture).format!=RenderingDevice.DATA_FORMAT_R16G16_SFLOAT:
			push_error("Unexpected temporal input texture format: depth="+str(depth_format)+" velocity="+str(rd.texture_get_format(velocity_texture).format));return
		var scene:RenderSceneDataRD=data.get_render_scene_data()
		var view:=scene.get_cam_transform().affine_inverse()
		var projection_matrix:=scene.get_cam_projection()
		var jitter_pixels:=scene.get_taa_jitter()*Vector2(size)*.5
		var rows:=[]
		var coordinates:=PackedByteArray();coordinates.resize(48)
		for point in points:
			var view_point:Vector3=view*point.world
			var clip:=projection_matrix*Vector4(view_point.x,view_point.y,view_point.z,1)
			var uv:=Vector2(clip.x,clip.y)/clip.w*.5+Vector2(.5,.5)
			var pixel:=Vector2i(uv*Vector2(size))
			coordinates.encode_s32(rows.size()*8,pixel.x);coordinates.encode_s32(rows.size()*8+4,pixel.y)
			rows.append({"label":point.label,"pixel":[pixel.x,pixel.y],"expected_depth":point.expected_depth,
				"depth_format":depth_format,
				"projection_depth":clip.z/clip.w,"expected_velocity":point.expected_velocity,
				"jitter_input_pixels":[jitter_pixels.x,jitter_pixels.y]})
		if super_resolution:
			mutex.lock();pending_readback={"buffers":buffers,"depth":depth_texture,"velocity":velocity_texture,"rows":rows,"coordinates":coordinates};mutex.unlock()
			return
		_sample_inputs(depth_texture,velocity_texture,rows,coordinates)
	func read_post_draw() -> void:
		RenderingServer.call_on_render_thread(_read_pending)
		RenderingServer.force_sync()
	func _read_pending() -> void:
		mutex.lock();var pending:=pending_readback;pending_readback={};mutex.unlock()
		if pending.is_empty():push_error("Missing deferred SR input readback");return
		_sample_inputs(pending.depth,pending.velocity,pending.rows,pending.coordinates)
	func _sample_inputs(depth_texture:RID,velocity_texture:RID,rows:Array,coordinates:PackedByteArray) -> void:
		var rd:=RenderingServer.get_rendering_device()
		if not probe_shader.is_valid():
			var source:=RDShaderSource.new();source.source_compute="""#version 450
layout(local_size_x=1,local_size_y=1,local_size_z=1) in;
layout(set=0,binding=0) uniform sampler2D depth_input;
layout(set=0,binding=1) uniform sampler2D velocity_input;
layout(set=0,binding=2,std430) buffer Samples { ivec4 coordinates; vec4 values[2]; } samples;
void main(){uint i=gl_GlobalInvocationID.x;ivec2 p=i==0u?samples.coordinates.xy:samples.coordinates.zw;
samples.values[i]=vec4(texelFetch(depth_input,p,0).r,texelFetch(velocity_input,p,0).rg,1.0);
}
"""
			probe_shader=rd.shader_create_from_spirv(rd.shader_compile_spirv_from_source(source))
			probe_pipeline=rd.compute_pipeline_create(probe_shader)
			probe_sampler=rd.sampler_create(RDSamplerState.new())
			probe_buffer=rd.storage_buffer_create(48,coordinates)
		else:rd.buffer_update(probe_buffer,0,48,coordinates)
		var uniforms:Array[RDUniform]=[]
		for index in 2:
			var uniform:=RDUniform.new();uniform.uniform_type=RenderingDevice.UNIFORM_TYPE_SAMPLER_WITH_TEXTURE;uniform.binding=index
			uniform.add_id(probe_sampler);uniform.add_id(depth_texture if index==0 else velocity_texture);uniforms.append(uniform)
		var storage:=RDUniform.new();storage.uniform_type=RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER;storage.binding=2;storage.add_id(probe_buffer);uniforms.append(storage)
		var uniform_set:=rd.uniform_set_create(uniforms,probe_shader,0)
		var list:=rd.compute_list_begin();rd.compute_list_bind_compute_pipeline(list,probe_pipeline)
		rd.compute_list_bind_uniform_set(list,uniform_set,0);rd.compute_list_dispatch(list,2,1,1);rd.compute_list_end()
		var values:=rd.buffer_get_data(probe_buffer);rd.free_rid(uniform_set)
		for index in rows.size():
			rows[index]["depth"]=values.decode_float(16+index*16)
			rows[index]["velocity"]=[values.decode_float(20+index*16),values.decode_float(24+index*16)]
		mutex.lock();observations=rows;mutex.unlock()
	func snapshot() -> Dictionary:
		mutex.lock();var result:=state.duplicate(true);mutex.unlock()
		for key in ["size","output_size"]:
			if result.has(key):
				var value:Vector2i=result[key]
				result[key]=[value.x,value.y]
		return result

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="):output=arg.trim_prefix("--output=")
		if arg.begins_with("--backend="):backend=arg.trim_prefix("--backend=")
		if arg.begins_with("--rr-preset="):rr_preset=arg.trim_prefix("--rr-preset=")
		if arg.begins_with("--sr-preset="):sr_preset=arg.trim_prefix("--sr-preset=")
		if arg=="--super-resolution":super_resolution=true
		if arg.begins_with("--scale="):scale=float(arg.trim_prefix("--scale="))
		if arg=="--inject-ghost":inject_ghost=true
		if arg.begins_with("--projection="):projection=arg.trim_prefix("--projection=")
		if arg.begins_with("--sharpening="):sharpening=float(arg.trim_prefix("--sharpening="))
		if arg=="--capture-inputs":capture_inputs=true
		if arg=="--reverse-motion":movement_direction=-1.0
		if arg in ["--opaque-particle-guides","--transparency-layer"]:
			push_error("Removed renderer experiment requested");quit(2);return
		if arg=="--ghost-writes-depth":ghost_writes_depth=true
		if arg.begins_with("--resolution="):
			var dimensions:=arg.trim_prefix("--resolution=").split("x")
			output_size=Vector2i(int(dimensions[0]),int(dimensions[1]))
	call_deferred("run")

func frames(count: int) -> void:
	for index in count:
		await process_frame
		await RenderingServer.frame_post_draw

func ready() -> bool:
	if backend!="dlss":return true
	var deadline:=Time.get_ticks_msec()+90000
	var stable:=0
	while Time.get_ticks_msec()<deadline:
		await frames(1)
		if super_resolution:
			var native:=observer.snapshot()
			stable=stable+1 if native.get("feature")=="SR" and native.get("evaluation_succeeded",false) and native.get("frames",0)>=32 else 0
			if stable>=16:return true
			continue
		var scene_ready:=RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_SCENE_READY)
		var pending:=RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_PENDING_MATERIALS)
		stable=stable+1 if scene_ready>0 and pending==0 else 0
		if stable>=16:return true
	push_error("Temporal fixture materials did not become ready");quit(3);return false

func quad(parent: Node3D,color: Color,unshaded: bool,size: Vector2) -> MeshInstance3D:
	var node:=MeshInstance3D.new();var mesh:=QuadMesh.new();mesh.size=size
	var material:=StandardMaterial3D.new();material.albedo_color=color
	material.metallic=0;material.roughness=1;material.metallic_specular=0
	if unshaded:material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	if color.a<1:material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	node.mesh=mesh;node.material_override=material;parent.add_child(node)
	return node

func bounds(center: Vector3) -> Rect2i:
	var a:=camera.unproject_position(center+Vector3(-.35,.35,0))
	var b:=camera.unproject_position(center+Vector3(.35,-.35,0))
	return Rect2i(Vector2i(a.ceil()),Vector2i(b.floor()-a.ceil()))

func foreground(image: Image,background: Image,rect: Rect2i) -> Dictionary:
	var center:=rect.get_center();var color:=Vector3.ZERO;var baseline:=0.0
	for y in range(center.y-3,center.y+4):
		for x in range(center.x-3,center.x+4):
			var pixel:=image.get_pixel(x,y)
			color+=Vector3(pixel.r,pixel.g,pixel.b);baseline+=background.get_pixel(x,y).r
	color/=49.0;baseline/=49.0
	return {"mean_rgb":[color.x,color.y,color.z],"red_excess":color.x-baseline,
		"visible":color.x-baseline>.15 and color.x>color.y*1.5 and color.x>color.z*1.5}

func trail(image: Image,background: Image,old: Rect2i,current: Rect2i) -> Dictionary:
	var values:Array[float]=[]
	var worst_position:=Vector2i.ZERO
	var worst_value:=-1.0
	var pixels_above_limit:=0
	var previous:=old.grow(-3).intersection(Rect2i(Vector2i.ZERO,image.get_size()))
	var protected_area:=current.grow(3)
	for y in range(previous.position.y,previous.end.y):
		for x in range(previous.position.x,previous.end.x):
			if protected_area.has_point(Vector2i(x,y)):continue
			var a:=image.get_pixel(x,y);var b:=background.get_pixel(x,y)
			var difference:=maxf(absf(a.r-b.r),maxf(absf(a.g-b.g),absf(a.b-b.b)))
			values.append(difference)
			if difference>worst_value:worst_value=difference;worst_position=Vector2i(x,y)
			if difference>TRAIL_LIMIT:pixels_above_limit+=1
	values.sort()
	if values.size()<30:return {"error":"Insufficient vacated pixels","samples":values.size()}
	return {"samples":values.size(),"p95_rgb_excess":values[floori((values.size()-1)*.95)],"max_rgb_excess":values[-1],
		"worst_position":[worst_position.x,worst_position.y],"pixels_above_limit":pixels_above_limit,
		"current_bounds":[current.position.x,current.position.y,current.end.x,current.end.y]}

func run() -> void:
	if output.is_empty() or DirAccess.dir_exists_absolute(output) or backend not in ["raster","dlss"] or scale not in [.45,.5,1.0] or projection not in ["perspective","orthographic"]:
		push_error("Choose a fresh output, valid backend and scale");quit(2);return
	if DirAccess.make_dir_recursive_absolute(output)!=OK:quit(2);return
	if backend=="dlss":
		if sr_preset!="default":Streamline.set_parameter(Streamline.STREAMLINE_PARAM_DLSS_PRESET,sr_preset)
		if rr_preset!="default":Streamline.set_parameter(Streamline.STREAMLINE_PARAM_DLSS_RR_PRESET,rr_preset)
		print("RT_TEMPORAL_RR_PRESET ",rr_preset)
		print("RT_TEMPORAL_SR_PRESET ",sr_preset)
	root.borderless=true;root.size=output_size;root.msaa_3d=Viewport.MSAA_DISABLED;root.use_taa=false
	root.scaling_3d_mode=Viewport.SCALING_3D_MODE_DLSS if backend=="dlss" else Viewport.SCALING_3D_MODE_BILINEAR
	root.scaling_3d_scale=scale if backend=="dlss" else 1.0
	if sharpening>=0:root.fsr_sharpness=sharpening
	stage=Node3D.new();root.add_child(stage)
	var world:=WorldEnvironment.new();world.environment=Environment.new();stage.add_child(world)
	world.environment.background_mode=Environment.BG_COLOR;world.environment.background_color=Color(.02,.02,.02)
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_DISABLED
	world.environment.tonemap_mode=Environment.TONE_MAPPER_LINEAR
	world.environment.set("pathtracing_enabled",backend=="dlss" and not super_resolution);world.environment.set("pathtracing_denoiser",1)
	world.environment.set("pathtracing_max_bounces",3);world.environment.set("pathtracing_samples_per_pixel",1)
	observer=Observer.new();observer.super_resolution=super_resolution;world.compositor=Compositor.new();world.compositor.compositor_effects=[observer]
	var backdrop:=quad(stage,Color(.02,.02,.02),true,Vector2(12,8));backdrop.position.z=-1
	var light:=DirectionalLight3D.new();stage.add_child(light);light.light_energy=1.25;light.shadow_enabled=false
	camera=Camera3D.new();stage.add_child(camera);camera.current=true
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL if projection=="orthographic" else Camera3D.PROJECTION_PERSPECTIVE
	camera.size=3.6;camera.fov=50;camera.position=Vector3(0,0,5)
	await frames(360)
	if not await ready():return
	var background:=root.get_texture().get_image()
	var rows:=[]
	for label in ["camera_motion","object_motion","particle_motion"]:
		var group:=Node3D.new();stage.add_child(group)
		var target:Node3D
		if label=="particle_motion":
			var particles:=GPUParticles3D.new();particles.amount=1;particles.lifetime=60
			particles.preprocess=.1;particles.local_coords=true;particles.use_fixed_seed=true;particles.seed=120
			particles.visibility_aabb=AABB(Vector3(-1,-1,-1),Vector3(2,2,2))
			var shader:=Shader.new();shader.code="shader_type particles;render_mode disable_velocity;void start(){TRANSFORM=mat4(1.0);COLOR=vec4(1.0);VELOCITY=vec3(0.0);}void process(){}"
			var process:=ShaderMaterial.new();process.shader=shader;particles.process_material=process
			var shape:=QuadMesh.new();shape.size=Vector2(.7,.7)
			var material:=StandardMaterial3D.new();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
			material.albedo_color=Color(.8,.03,.03);shape.material=material
			particles.draw_pass_1=shape;group.add_child(particles);target=particles
		else:target=quad(group,Color(.8,.03,.03),false,Vector2(.7,.7))
		target.position=Vector3(0 if label=="camera_motion" else -1.2*movement_direction,0,1)
		camera.position.x=-1.2*movement_direction if label=="camera_motion" else 0.0
		var ghost:=quad(group,Color(.8,.03,.03,.5),true,Vector2(.7,.7));ghost.visible=false
		if ghost_writes_depth:
			var ghost_material:=ghost.material_override as BaseMaterial3D
			ghost_material.depth_draw_mode=BaseMaterial3D.DEPTH_DRAW_ALWAYS
			# Particle AABBs influence alpha sorting. The control must draw after
			# the opaque target, otherwise its depth can prevent that target drawing.
			ghost_material.render_priority=127
		await frames(120)
		if not await ready():return
		await frames(16)
		# Cover the complete half-resolution Halton cycle at the same phase in
		# each run; differing material compile times must not choose the phase.
		while Engine.get_frames_drawn()%32!=0:await frames(1)
		var before:=observer.snapshot()
		var previous:=bounds(target.global_position)
		var samples:=[]
		for step in STEPS:
			var previous_center:=target.global_position;var previous_camera:=camera.position.x
			var previous_uv:=camera.unproject_position(previous_center)/Vector2(root.size)
			# Keep the background sample vertically clear of every target pose;
			# world-space X separation alone does not prevent perspective overlap.
			var background_point:=Vector3(0,1.2,-1)
			var previous_background_uv:=camera.unproject_position(background_point)/Vector2(root.size)
			if label=="camera_motion":camera.position.x=(-1.2+(step+1)*.1)*movement_direction
			else:target.position.x=(-1.2+(step+1)*.1)*movement_direction
			ghost.position=previous_center+Vector3(camera.position.x-previous_camera,0,.01)
			ghost.visible=inject_ghost
			if capture_inputs and backend=="dlss":
				var expected_uv:=previous_uv-camera.unproject_position(target.global_position)/Vector2(root.size)
				var background_uv:=previous_background_uv-camera.unproject_position(background_point)/Vector2(root.size)
				if label=="particle_motion" and not super_resolution:expected_uv=Vector2.ZERO
				var unjittered:=camera.get_camera_projection()
				var correction:=Projection.create_depth_correction(true)
				var expected_target:=correction*unjittered*Vector4(0,0,-6 if label=="particle_motion" and not super_resolution else -4,1)
				var expected_background:=correction*unjittered*Vector4(0,0,-6,1)
				observer.arm([{"label":"target","world":target.global_position,"expected_depth":expected_target.z/expected_target.w,"expected_velocity":[expected_uv.x,expected_uv.y]},
					{"label":"background","world":background_point,"expected_depth":expected_background.z/expected_background.w,"expected_velocity":[background_uv.x,background_uv.y]}])
			await frames(1)
			if capture_inputs and backend=="dlss" and super_resolution:observer.read_post_draw()
			var image:=root.get_texture().get_image()
			var current:=bounds(target.global_position)
			var sample:=trail(image,background,previous,current)
			sample["foreground"]=foreground(image,background,current)
			if capture_inputs and backend=="dlss":sample["inputs"]=observer.input_samples()
			if sample.has("error"):push_error(str(sample));quit(3);return
			sample["step"]=step;samples.append(sample)
			if step in [0,5,11,17,23,31] or (not inject_ghost and sample.max_rgb_excess>.3):image.save_png(output.path_join(label+"_%02d.png"%step))
			previous=current
		await frames(2)
		var after:=observer.snapshot()
		if backend=="dlss" and (after.get("backend")!="DLSS" or not after.get("viewport_renderer",false) or not after.get("evaluation_succeeded",false) or int(after.get("frames",0))-int(before.get("frames",0))<STEPS or int(after.get("resets",0))-int(before.get("resets",0))>1):
			push_error("Missing native "+("SR" if super_resolution else "RR")+" motion continuity: "+JSON.stringify({"before":before,"after":after}));quit(3);return
		rows.append({"case":label,"samples":samples,"before":before,"after":after})
		group.queue_free();await frames(2)
	FileAccess.open(output.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({"captured":true,
		"backend":backend,"rr_preset":rr_preset,"sr_preset":sr_preset,"super_resolution":super_resolution,"projection":projection,"movement_direction":movement_direction,"output_size":[root.size.x,root.size.y],"scale":root.scaling_3d_scale,"sharpening":root.fsr_sharpness,"trail_limit":TRAIL_LIMIT,"injected_ghost":inject_ghost,"cases":rows},"\t"))
	print("RT_TEMPORAL_EDGES_CAPTURED")
	observer.release();stage.queue_free();await frames(3);quit()
