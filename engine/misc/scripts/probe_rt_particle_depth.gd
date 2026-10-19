extends SceneTree
## Analytical overlapping-particle fixtures. A separate comparison must check
## raster reference, the previous RT path and the opt-in candidate.
var output := ""
var backend := "raster"
var scale := 1.0
var camera: Camera3D
var stage: Node3D

class ReconstructionObserver extends CompositorEffect:
	var mutex := Mutex.new()
	var value := {}
	var callbacks := 0
	func _init() -> void:
		effect_callback_type=EFFECT_CALLBACK_TYPE_POST_TRANSPARENT
		access_resolved_color=true
	func _render_callback(_type: int,data: RenderData) -> void:
		var buffers: RenderSceneBuffersRD=data.get_render_scene_buffers()
		var observed: Dictionary=buffers.get_meta("dlss_diagnostics",{})
		mutex.lock();value=observed.duplicate(true);callbacks+=1;mutex.unlock()
	func snapshot() -> Dictionary:
		mutex.lock();var result:=value.duplicate(true);result["callback_frames"]=callbacks;mutex.unlock()
		for key in ["size","output_size"]:
			if result.has(key):
				var dimensions: Vector2i=result[key]
				result[key]=[dimensions.x,dimensions.y]
		return result

const PROCESS := """shader_type particles;
render_mode disable_velocity;
void start() {
 TRANSFORM = mat4(1.0);
 TRANSFORM[3].z = INDEX == 0u ? 1.0 : -1.0;
 COLOR = INDEX == 0u ? vec4(0.9,0.02,0.02,1.0) : vec4(0.02,0.02,0.9,1.0);
 VELOCITY = vec3(0.0);
}
void process() {}
"""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="): output=arg.trim_prefix("--output=")
		if arg.begins_with("--backend="): backend=arg.trim_prefix("--backend=")
		if arg.begins_with("--scale="): scale=float(arg.trim_prefix("--scale="))
	call_deferred("run")

func plane(parent: Node3D,z: float,size: Vector2,color: Color) -> MeshInstance3D:
	var node := MeshInstance3D.new();var shape := QuadMesh.new();shape.size=size
	var material := StandardMaterial3D.new();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color=color
	if color.a<1.0: material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	node.mesh=shape;node.material_override=material;node.position.z=z;parent.add_child(node)
	return node

func color_region(image: Image,world_point: Vector3) -> Array:
	var center := Vector2i(camera.unproject_position(world_point))
	var sum := Vector3.ZERO
	for y in range(center.y-5,center.y+6):
		for x in range(center.x-5,center.x+6):
			var pixel := image.get_pixel(x,y)
			sum+=Vector3(pixel.r,pixel.g,pixel.b)
	sum/=121.0
	return [sum.x,sum.y,sum.z]

func run() -> void:
	if output.is_empty() or backend not in ["raster","rt"] or scale not in [0.5,1.0] or DirAccess.dir_exists_absolute(output):
		push_error("Choose a fresh output and valid backend");quit(2);return
	if DirAccess.make_dir_recursive_absolute(output)!=OK: quit(2);return
	root.size=Vector2i(640,360)
	root.msaa_3d=Viewport.MSAA_DISABLED;root.use_taa=false
	root.scaling_3d_mode=Viewport.SCALING_3D_MODE_DLSS if backend=="rt" else Viewport.SCALING_3D_MODE_BILINEAR
	root.scaling_3d_scale=scale if backend=="rt" else 1.0
	stage=Node3D.new();root.add_child(stage)
	var world := WorldEnvironment.new();world.environment=Environment.new();stage.add_child(world)
	world.environment.background_mode=Environment.BG_COLOR;world.environment.background_color=Color(0.02,0.02,0.02)
	world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_DISABLED
	world.environment.tonemap_mode=Environment.TONE_MAPPER_LINEAR
	world.environment.set("pathtracing_enabled",backend=="rt")
	world.environment.set("pathtracing_denoiser",1)
	world.environment.set("pathtracing_max_bounces",3)
	world.environment.set("pathtracing_samples_per_pixel",1)
	var observer := ReconstructionObserver.new()
	world.compositor=Compositor.new();world.compositor.compositor_effects=[observer]
	plane(stage,-3.0,Vector2(12,8),Color(0.02,0.02,0.02))
	camera=Camera3D.new();stage.add_child(camera);camera.current=true
	camera.position=Vector3(0,0,5);camera.look_at(Vector3.ZERO)
	var rows := []
	for label in ["opaque","cutout","instance_fade","opaque_cover","transparent_front"]:
		var group := Node3D.new();stage.add_child(group)
		var particles := GPUParticles3D.new()
		particles.amount=2;particles.lifetime=60.0;particles.preprocess=0.1
		particles.explosiveness=1.0;particles.local_coords=true
		particles.draw_order=GPUParticles3D.DRAW_ORDER_INDEX
		particles.visibility_aabb=AABB(Vector3(-2,-2,-2),Vector3(4,4,4))
		var process_shader := Shader.new();process_shader.code=PROCESS
		var process_material := ShaderMaterial.new();process_material.shader=process_shader
		particles.process_material=process_material
		var material_shader := Shader.new()
		var code := "shader_type spatial; render_mode unshaded; void fragment(){ALBEDO=COLOR.rgb;"
		if label=="cutout": code+="ALPHA=COLOR.r>0.5 ? step(0.5,UV.x) : 1.0; ALPHA_SCISSOR_THRESHOLD=0.5;"
		material_shader.code=code+"}"
		var material := ShaderMaterial.new();material.shader=material_shader
		var shape := QuadMesh.new();shape.size=Vector2(2,2);shape.material=material
		particles.draw_pass_1=shape
		if label=="instance_fade": particles.transparency=0.5
		group.add_child(particles)
		if label=="opaque_cover": plane(group,2.0,Vector2(1.5,1.5),Color(0.02,0.9,0.02))
		if label=="transparent_front": plane(group,2.0,Vector2(1.5,1.5),Color(0.02,0.9,0.02,0.5))
		var started := Time.get_ticks_msec()
		var frames := 0
		while frames<240 or Time.get_ticks_msec()-started<3000:
			await RenderingServer.frame_post_draw;frames+=1
		var image := root.get_texture().get_image()
		var center := color_region(image,Vector3.ZERO)
		var left := color_region(image,Vector3(-0.45,0,1))
		var right := color_region(image,Vector3(0.45,0,1))
		var reconstruction := observer.snapshot()
		if backend=="rt" and (reconstruction.get("backend")!="DLSS" or not reconstruction.get("viewport_renderer",false) or not reconstruction.get("evaluation_succeeded",false) or int(reconstruction.get("frames",0))<60):
			push_error("Missing successful native RR evaluations: "+label+" "+JSON.stringify({"observed":reconstruction,"mode":root.scaling_3d_mode,"scale":root.scaling_3d_scale}));quit(3);return
		if backend=="rt" and (reconstruction.get("size")!=[int(640*scale),int(360*scale)] or reconstruction.get("output_size")!=[640,360]):
			push_error("Unexpected RR input/output dimensions");quit(3);return
		if maxf(center[0],maxf(center[1],center[2]))<0.15:
			push_error("Particle fixture did not become visible: "+label);quit(3);return
		image.save_png(output.path_join(label+".png"))
		rows.append({"case":label,"center":center,"left":left,"right":right,"frames":frames,"reconstruction":reconstruction})
		group.queue_free();await process_frame;await process_frame
	FileAccess.open(output.path_join("report.json"),FileAccess.WRITE).store_string(JSON.stringify({
		"captured":true,"qualified":false,"backend":backend,"scale":root.scaling_3d_scale,"opaque_depth_requested":OS.get_environment("GODOT_RT_OPAQUE_PARTICLE_DEPTH"),"cases":rows},"\t"))
	print("RT_PARTICLE_DEPTH_CAPTURED")
	quit()
