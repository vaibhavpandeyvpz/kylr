extends SceneTree
class_name RTUnshadedFixture
## Spatial constancy of opaque, unshaded instance colors through reconstruction.
## No application assets. Early captures diagnose settling; only the last gates.
var output := ""
var backend := "dlss"
var scale := 0.5
var studio := false
var transition := false
var camera_cut := false
var camera_motion := false

class ReactiveProbe extends CompositorEffect:
	var mutex := Mutex.new()
	var requested := false
	var sample_uv := Vector2.ZERO
	var result: Dictionary = {}
	func _init():
		effect_callback_type=CompositorEffect.EFFECT_CALLBACK_TYPE_POST_TRANSPARENT
		access_resolved_color=true
	func arm(uv: Vector2):
		mutex.lock();sample_uv=uv;requested=true;mutex.unlock()
	func read() -> Dictionary:
		mutex.lock();var value:=result.duplicate();mutex.unlock();return value
	func _render_callback(_type: int, data: RenderData):
		mutex.lock();var capture:=requested;var uv:=sample_uv;requested=false;mutex.unlock()
		if not capture:return
		var buffers:RenderSceneBuffersRD=data.get_render_scene_buffers()
		var size:=buffers.get_internal_size()
		var rd:=RenderingServer.get_rendering_device()
		# Scene color is sampleable, but not necessarily copyable. Read the
		# actual alpha through a one-invocation shader into an owned buffer.
		var source:=RDShaderSource.new()
		source.source_compute="#version 450\nlayout(local_size_x=1,local_size_y=1,local_size_z=1) in; layout(set=0,binding=0) uniform sampler2D scene_color; layout(set=0,binding=1,std430) buffer Result {float alpha;}; layout(push_constant,std430) uniform Params {ivec2 pixel;} params; void main(){alpha=texelFetch(scene_color,params.pixel,0).a;}"
		var spirv:=rd.shader_compile_spirv_from_source(source)
		if not spirv.compile_error_compute.is_empty():push_error(spirv.compile_error_compute);return
		var shader:=rd.shader_create_from_spirv(spirv)
		var pipeline:=rd.compute_pipeline_create(shader)
		var sampler:=rd.sampler_create(RDSamplerState.new())
		var buffer:=rd.storage_buffer_create(4)
		var color_uniform:=RDUniform.new();color_uniform.uniform_type=RenderingDevice.UNIFORM_TYPE_SAMPLER_WITH_TEXTURE;color_uniform.binding=0
		color_uniform.add_id(sampler);color_uniform.add_id(buffers.get_color_layer(0))
		var result_uniform:=RDUniform.new();result_uniform.uniform_type=RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER;result_uniform.binding=1;result_uniform.add_id(buffer)
		var uniforms:=rd.uniform_set_create([color_uniform,result_uniform],shader,0)
		var pixel:=Vector2i(uv*Vector2(size))
		var constants:=PackedInt32Array([pixel.x,pixel.y]).to_byte_array()
		var list:=rd.compute_list_begin();rd.compute_list_bind_compute_pipeline(list,pipeline);rd.compute_list_bind_uniform_set(list,uniforms,0)
		rd.compute_list_set_push_constant(list,constants,constants.size());rd.compute_list_dispatch(list,1,1,1);rd.compute_list_end()
		var bytes:=rd.buffer_get_data(buffer)
		var value:Dictionary={"passed":false,"bytes":bytes.size(),"size":str(size)}
		if bytes.size()==4:
			var alpha:=bytes.decode_float(0)
			value["alpha"]=alpha;value["passed"]=absf(alpha)<.001
		for resource in [uniforms,pipeline,shader,buffer,sampler]:rd.free_rid(resource)
		mutex.lock();result=value;mutex.unlock()

func _initialize(): run.call_deferred()

func flatness(image: Image, center: Vector2, radius: float, channel: int) -> Dictionary:
	var values: Array[float] = []
	for y in range(ceili(center.y-radius),floori(center.y+radius)+1):
		for x in range(ceili(center.x-radius),floori(center.x+radius)+1):
			if Vector2(x,y).distance_to(center)>radius:continue
			values.append(image.get_pixel(x,y)[channel])
	values.sort()
	var low := values[floori((values.size()-1)*.01)]
	var high := values[floori((values.size()-1)*.99)]
	return {"samples":values.size(),"p01":low,"p99":high,"spread":high-low,"passed":low>.15 and high-low<.03}

func run():
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):output=argument.trim_prefix("--output=")
		if argument.begins_with("--backend="):backend=argument.trim_prefix("--backend=")
		if argument.begins_with("--scale="):scale=float(argument.trim_prefix("--scale="))
		if argument=="--studio":studio=true
		if argument=="--transition":transition=true
		if argument=="--camera-cut":camera_cut=true
		if argument=="--camera-motion":camera_motion=true
	if output.is_empty() or backend not in ["raw","dlss","raster-fsr2"] or scale not in [.5,1.0]:quit(2);return
	var fsr2:=backend.ends_with("-fsr2")
	if (camera_cut or camera_motion) and not fsr2:quit(2);return
	if backend!="dlss" and not fsr2 and scale!=1.0:quit(2);return
	if FileAccess.file_exists(output.path_join("report.json")):push_error("Preserve previous results");quit(2);return
	if DirAccess.make_dir_recursive_absolute(output)!=OK:quit(2);return
	root.size=Vector2i(1280,720)
	root.scaling_3d_mode=Viewport.SCALING_3D_MODE_DLSS if backend=="dlss" else Viewport.SCALING_3D_MODE_BILINEAR
	if fsr2:root.scaling_3d_mode=Viewport.SCALING_3D_MODE_FSR2
	root.scaling_3d_scale=scale;root.use_taa=false;root.msaa_3d=Viewport.MSAA_DISABLED
	root.screen_space_aa=Viewport.SCREEN_SPACE_AA_DISABLED
	if backend=="dlss" and (not Engine.has_singleton("Streamline") or not Engine.get_singleton("Streamline").get_capability(2)):
		push_error("Ray Reconstruction unavailable");quit(2);return
	var stage:=Node3D.new();root.add_child(stage)
	var world:=WorldEnvironment.new();world.environment=Environment.new();stage.add_child(world)
	world.environment.background_mode=Environment.BG_COLOR
	world.environment.background_color=Color(.04,.05,.06)
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_DISABLED
	world.environment.set("pathtracing_enabled",backend!="raster-fsr2")
	world.environment.set("pathtracing_denoiser",{"raw":0,"dlss":1,"raster-fsr2":0}[backend])
	world.environment.set("pathtracing_max_bounces",4)
	var reactive_probe:ReactiveProbe
	if fsr2:
		reactive_probe=ReactiveProbe.new()
		var compositor:=Compositor.new();compositor.compositor_effects=[reactive_probe];world.compositor=compositor
	if studio:
		world.environment.tonemap_mode=Environment.TONE_MAPPER_FILMIC
		world.environment.glow_enabled=true;world.environment.glow_intensity=.12
		for settings in [[Vector3(2.5,3,2.5),4.,Vector2(1.6,1.6)],[Vector3(-2,1.8,1.2),1.4,Vector2(1.8,1.8)],[Vector3(-1.2,2.5,-2),3.,Vector2(1,1.6)]]:
			var area:=AreaLight3D.new();area.position=settings[0];area.light_energy=settings[1]
			area.area_size=settings[2];area.area_range=8;area.shadow_enabled=true;stage.add_child(area);area.look_at(Vector3(0,.9,0))
	var floor_mesh:=MeshInstance3D.new();var plane:=PlaneMesh.new();plane.size=Vector2(30,30)
	floor_mesh.mesh=plane;stage.add_child(floor_mesh)
	var material:=StandardMaterial3D.new();material.albedo_color=Color(.27,.30,.33);material.roughness=1.0
	floor_mesh.material_override=material
	var light:=DirectionalLight3D.new();light.rotation_degrees=Vector3(-50,-30,0);light.shadow_enabled=true;stage.add_child(light)
	var shader:=Shader.new()
	shader.code="shader_type spatial; render_mode unshaded; instance uniform vec4 effect_tint : source_color = vec4(1.0); instance uniform float effect_phase = 0.0; varying float pulse; void vertex(){pulse=effect_phase;} void fragment(){ALBEDO=effect_tint.rgb*(0.8+0.2*sin(pulse));}"
	var shared:=ShaderMaterial.new();shared.shader=shader
	var centers:Array[Vector3]=[]
	var spheres:Array[MeshInstance3D]=[]
	for index in 2:
		var sphere:=MeshInstance3D.new();var mesh:=SphereMesh.new();mesh.radius=.25;mesh.height=.5
		sphere.mesh=mesh;sphere.material_override=shared;stage.add_child(sphere)
		sphere.position=Vector3(-.35 if index==0 else .35,1,0)
		sphere.set_instance_shader_parameter("effect_tint",Color(1,.01,.01) if index==0 else Color(.01,.01,1))
		sphere.set_instance_shader_parameter("effect_phase",float(index));centers.append(sphere.position)
		spheres.append(sphere)
		if transition:sphere.material_override=material
	var camera:=Camera3D.new();stage.add_child(camera);camera.current=true;camera.fov=50
	if fsr2:camera.near=.1
	camera.position=Vector3(0,1,0)+Vector3(0,1.8*.22,1.8);camera.look_at(Vector3(0,1,0))
	var started:=Time.get_ticks_msec();var stable:=0
	while Time.get_ticks_msec()-started<120000:
		await process_frame;await RenderingServer.frame_post_draw
		var ready:=backend=="raster-fsr2" or RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_SCENE_READY)>0
		var pending:=RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,RenderingServer.VIEWPORT_RENDER_INFO_RT_PENDING_MATERIALS)
		stable=stable+1 if ready and pending==0 else 0
		if stable>=8:break
	if stable<8:push_error("RT unshaded fixture not ready");quit(3);return
	if transition:
		for frame in 64:await RenderingServer.frame_post_draw
		for sphere in spheres:sphere.material_override=shared
		# Observe material replacement, including the first reconstruction frames.
		await process_frame
	var captures:=[];var passed:=true
	for frame in 361:
		if camera_motion:
			camera.position.x+=.0005
			camera.look_at(Vector3(0,1,0))
		if camera_cut and frame==180:
			camera.position.z=-1.8
			camera.look_at(Vector3(0,1,0))
			print("RT_UNSHADED_CAMERA_CUT")
		await process_frame;await RenderingServer.frame_post_draw
		if frame not in [1,24,120,360] and not (camera_cut and frame==181):continue
		var image:=root.get_texture().get_image()
		if image.get_size()!=Vector2i(1280,720):push_error("Unexpected output size");quit(3);return
		var colors:=[]
		for index in 2:
			var center:=camera.unproject_position(centers[index])
			var radius:=center.distance_to(camera.unproject_position(centers[index]+camera.global_basis.x*.25))*.65
			colors.append(flatness(image,center,radius,0 if index==0 else 2))
		if image.save_png(output.path_join("frame-%03d.png"%frame))!=OK:quit(3);return
		captures.append({"frame":frame,"colors":colors})
		print("RT_UNSHADED_FRAME ",frame)
		if frame==360 or (camera_cut and frame==181):passed=passed and colors[0].passed and colors[1].passed
	var flatness_passed:=passed
	var reactive_alpha:Dictionary={}
	if fsr2:
		reactive_probe.arm(camera.unproject_position(centers[0])/Vector2(root.size))
		await process_frame;await RenderingServer.frame_post_draw
		reactive_alpha=reactive_probe.read()
		passed=passed and reactive_alpha.get("passed",false)
	var report:={"passed":passed,"flatness_passed":flatness_passed,"backend":backend,"scale":scale,"studio":studio,"transition":transition,"camera_cut":camera_cut,"camera_motion":camera_motion,"camera_fov":camera.fov,"captures":captures,"reactive_alpha":reactive_alpha,"engine":Engine.get_version_info(),"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),"performance_accepted":false,"full_scene_quality_accepted":false}
	FileAccess.open(output.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify(report,"\t"))
	print("RT_UNSHADED_CAPTURE_DONE ",backend," passed=",passed)
	stage.queue_free()
	for frame in 8:await process_frame
	quit()
