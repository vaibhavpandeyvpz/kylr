extends SceneTree
## GPU readback of indexed geometry, TLAS transforms, custom IDs and ray masks.
## Run graphically with Vulkan validation; the dummy renderer cannot test this.
var rd: RenderingDevice
var owned: Array[RID] = []

func _initialize() -> void:
	run.call_deferred()

func keep(value: RID) -> RID:
	assert(value.is_valid(), "GPU resource creation failed")
	owned.append(value)
	return value

func run() -> void:
	create_timer(60).timeout.connect(func():push_error("Ray query probe timed out");quit(4))
	rd=RenderingServer.create_local_rendering_device()
	if rd==null or not rd.has_feature(RenderingDevice.SUPPORTS_RAY_QUERY):
		push_error("Vulkan ray query support is required")
		quit(2)
		return
	var vertices:=PackedVector3Array([Vector3(-.5,-.5,0),Vector3(.5,-.5,0),Vector3(0,.5,0)]).to_byte_array()
	var flags:=RenderingDevice.BUFFER_CREATION_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT | RenderingDevice.BUFFER_CREATION_DEVICE_ADDRESS_BIT
	var vertex_buffer:=keep(rd.vertex_buffer_create(vertices.size(),vertices,flags))
	var index_buffer:=keep(rd.index_buffer_create(3,RenderingDevice.INDEX_BUFFER_FORMAT_UINT32,PackedInt32Array([0,1,2]).to_byte_array(),false,flags))
	var geometry:=RDAccelerationStructureGeometry.new()
	geometry.flags=RenderingDevice.ACCELERATION_STRUCTURE_GEOMETRY_OPAQUE_BIT
	geometry.vertex_buffer=vertex_buffer
	geometry.vertex_stride=12
	geometry.vertex_format=RenderingDevice.DATA_FORMAT_R32G32B32_SFLOAT
	geometry.vertex_count=3
	geometry.index_buffer=index_buffer
	geometry.index_count=3
	var blas:=keep(rd.blas_create([geometry],0))
	var tlas:=keep(rd.tlas_create(2,0))
	rd.blas_build(blas)
	# The current TLAS API requires a real allocated SBT range even for inline
	# queries, which do not access hit shaders. Do not invent an encoded handle.
	var rt_source:=RDShaderSource.new()
	var empty_stage:="#version 460\n#extension GL_EXT_ray_tracing : require\nvoid main() {}\n"
	rt_source.set_stage_source(RenderingDevice.SHADER_STAGE_RAYGEN,empty_stage)
	rt_source.set_stage_source(RenderingDevice.SHADER_STAGE_CLOSEST_HIT,empty_stage)
	var rt_shader:=keep(rd.shader_create_from_spirv(rd.shader_compile_spirv_from_source(rt_source),"Query fixture SBT"))
	var rt_stage:=RDPipelineShader.new()
	rt_stage.shader=rt_shader
	var hit:=RDHitGroup.new()
	hit.closest_hit_shader=rt_stage
	var rt_pipeline:=keep(rd.raytracing_pipeline_create([rt_stage],[],[hit],1))
	var sbt:=keep(rd.hit_sbt_create(rt_pipeline,1))
	var sbt_range:=rd.hit_sbt_range_alloc(sbt,1)
	assert(rd.hit_sbt_range_update(sbt,sbt_range,0,PackedInt32Array([0]))==OK)
	var instances: Array[RDAccelerationStructureInstance]=[]
	for index in 2:
		var instance:=RDAccelerationStructureInstance.new()
		instance.blas=blas
		instance.id=0x13579 if index==0 else 0x2468
		instance.mask=0x80 if index==0 else 0x02
		instance.hit_sbt_range=sbt_range
		instance.flags=RenderingDevice.ACCELERATION_STRUCTURE_INSTANCE_TRIANGLE_FACING_CULL_DISABLE_BIT
		instance.transform.origin.x=index*2.0
		instances.append(instance)
	rd.tlas_build(tlas,instances)
	var source:=RDShaderSource.new()
	source.source_compute="""#version 460
#extension GL_EXT_ray_query : require
layout(local_size_x=1,local_size_y=1,local_size_z=1) in;
layout(set=0,binding=0) uniform accelerationStructureEXT scene;
layout(set=0,binding=1,std430) buffer Results { uint values[]; } result;
void main() {
    for (uint i=0u;i<3u;i++) {
        rayQueryEXT query;
        uint mask=i==1u ? 2u : 128u;
        rayQueryInitializeEXT(query,scene,gl_RayFlagsOpaqueEXT,mask,vec3(i==0u ? 0.0 : 2.0,0.0,1.0),0.001,vec3(0,0,-1),10.0);
        while (rayQueryProceedEXT(query)) {}
        bool hit=rayQueryGetIntersectionTypeEXT(query,true)==gl_RayQueryCommittedIntersectionTriangleEXT;
        result.values[2u*i]=hit ? uint(rayQueryGetIntersectionInstanceCustomIndexEXT(query,true)) : 0u;
        result.values[2u*i+1u]=hit ? floatBitsToUint(rayQueryGetIntersectionTEXT(query,true)) : 0u;
    }
}
"""
	var spirv:=rd.shader_compile_spirv_from_source(source)
	assert(spirv.get_stage_compile_error(RenderingDevice.SHADER_STAGE_COMPUTE).is_empty(),spirv.get_stage_compile_error(RenderingDevice.SHADER_STAGE_COMPUTE))
	var shader:=keep(rd.shader_create_from_spirv(spirv,"Ray query instance regression"))
	var output:=keep(rd.storage_buffer_create(24,PackedInt32Array([0,0,0,0,0,0]).to_byte_array()))
	var scene_uniform:=RDUniform.new()
	scene_uniform.uniform_type=RenderingDevice.UNIFORM_TYPE_ACCELERATION_STRUCTURE
	scene_uniform.binding=0
	scene_uniform.add_id(tlas)
	var output_uniform:=RDUniform.new()
	output_uniform.uniform_type=RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	output_uniform.binding=1
	output_uniform.add_id(output)
	var uniforms:=keep(rd.uniform_set_create([scene_uniform,output_uniform],shader,0))
	var pipeline:=keep(rd.compute_pipeline_create(shader))
	var commands:=rd.compute_list_begin()
	rd.compute_list_bind_compute_pipeline(commands,pipeline)
	rd.compute_list_bind_uniform_set(commands,uniforms,0)
	rd.compute_list_dispatch(commands,1,1,1)
	rd.compute_list_end()
	rd.submit()
	rd.sync()
	var bytes:=rd.buffer_get_data(output)
	var passed:=bytes.size()==24 and bytes.decode_u32(0)==0x13579 and bytes.decode_u32(8)==0x2468 and bytes.decode_u32(16)==0 and is_equal_approx(bytes.decode_float(4),1.0) and is_equal_approx(bytes.decode_float(12),1.0)
	# Free dependents before their buffers/acceleration structures.
	owned.reverse()
	for resource in owned:
		rd.free_rid(resource)
	owned.clear()
	rd.free()
	# Exercise the main renderer's frame-token path after local-device teardown.
	# Previously that teardown called global slShutdown and broke later frames.
	for frame in 6:await process_frame
	if passed and Engine.has_singleton("Streamline") and Engine.get_singleton("Streamline").get_capability(0) and Engine.get_singleton("Streamline").get_capability(2):
		passed=await check_reconstruction()
	if passed:print("RAY_QUERY_GPU_PASS indexed_triangle=1 instances=2 hit_masks=2 miss_masks=1");quit()
	else:push_error("Ray query instance GPU readback failed");quit(3)

func check_reconstruction() -> bool:
	# Ensure local compute work did not replace the SDK's logical device, in
	# addition to verifying that the main frame-token path remains initialized.
	root.size=Vector2i(640,360)
	root.scaling_3d_mode=Viewport.SCALING_3D_MODE_DLSS
	root.scaling_3d_scale=.5
	var stage:=Node3D.new()
	root.add_child(stage)
	var world:=WorldEnvironment.new()
	world.environment=Environment.new()
	world.environment.background_mode=Environment.BG_COLOR
	world.environment.background_color=Color(.1,.1,.1)
	world.environment.set("pathtracing_enabled",true)
	world.environment.set("pathtracing_denoiser",1)
	stage.add_child(world)
	var camera:=Camera3D.new()
	stage.add_child(camera)
	camera.position=Vector3(0,2,5)
	camera.look_at(Vector3(0,.6,0))
	camera.current=true
	var light:=DirectionalLight3D.new()
	stage.add_child(light)
	light.rotation_degrees=Vector3(-50,-30,0)
	var floor_node:=MeshInstance3D.new()
	var floor_mesh:=PlaneMesh.new()
	floor_mesh.size=Vector2(12,12)
	floor_node.mesh=floor_mesh
	stage.add_child(floor_node)
	var sphere:=MeshInstance3D.new()
	sphere.mesh=SphereMesh.new()
	sphere.position.y=.7
	stage.add_child(sphere)
	var ready_key:=ClassDB.class_get_integer_constant("RenderingServer","VIEWPORT_RENDER_INFO_RT_SCENE_READY")
	var ready:=false
	for frame in 240:
		await RenderingServer.frame_post_draw
		if frame>12 and RenderingServer.viewport_get_render_info(root.get_viewport_rid(),RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,ready_key)>0:
			ready=true
			break
	stage.queue_free()
	for frame in 6:await process_frame
	if ready:print("RAY_QUERY_RR_AFTER_LOCAL_PASS")
	else:push_error("Ray Reconstruction did not become ready after local-device teardown")
	return ready
