extends SceneTree
## Mixed shader layouts must not replay stale push constants across a compute barrier.
var output:=""
func _initialize():
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):output=argument.trim_prefix("--output=")
	run.call_deferred()

func run():
	if output.is_empty() or FileAccess.file_exists(output):quit(2);return
	var rd:=RenderingServer.create_local_rendering_device()
	if rd==null:quit(2);return
	var owned:Array[RID]=[];var shaders:Array[RID]=[];var pipelines:Array[RID]=[];var sets:Array[RID]=[]
	var format:=RDTextureFormat.new();format.width=1;format.height=1;format.format=RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT
	format.usage_bits=RenderingDevice.TEXTURE_USAGE_STORAGE_BIT|RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT
	var target:=rd.texture_create(format,RDTextureView.new());owned.append(target)
	var common:="#version 450\nlayout(local_size_x=1,local_size_y=1,local_size_z=1) in;\nlayout(rgba32f,set=0,binding=0) uniform image2D target;\n"
	var sources:=[common+"layout(push_constant,std430) uniform Params{vec4 value;}p;\nvoid main(){imageStore(target,ivec2(0),p.value);}",
		common+"void main(){imageStore(target,ivec2(0),imageLoad(target,ivec2(0))*2.);}",
		common+"layout(push_constant,std430) uniform Params{vec2 value;}p;\nvoid main(){imageStore(target,ivec2(0),imageLoad(target,ivec2(0))+vec4(p.value,0,0));}"]
	for text in sources:
		var source:=RDShaderSource.new();source.source_compute=text
		var spirv:=rd.shader_compile_spirv_from_source(source)
		if not spirv.compile_error_compute.is_empty():push_error(spirv.compile_error_compute);quit(3);return
		var shader:=rd.shader_create_from_spirv(spirv);owned.append(shader);shaders.append(shader)
		var pipeline:=rd.compute_pipeline_create(shader);owned.append(pipeline);pipelines.append(pipeline)
		var uniform:=RDUniform.new();uniform.uniform_type=RenderingDevice.UNIFORM_TYPE_IMAGE;uniform.binding=0;uniform.add_id(target)
		var set:=rd.uniform_set_create([uniform],shader,0);owned.append(set);sets.append(set)
	var list:=rd.compute_list_begin()
	for stage in [0,1,2,1]:
		rd.compute_list_bind_compute_pipeline(list,pipelines[stage]);rd.compute_list_bind_uniform_set(list,sets[stage],0)
		if stage!=1:
			var push:=PackedFloat32Array([.25,.5,.75,1.] if stage==0 else [.1,.2]).to_byte_array()
			rd.compute_list_set_push_constant(list,push,push.size())
		rd.compute_list_dispatch(list,1,1,1);rd.compute_list_add_barrier(list)
	rd.compute_list_end();rd.submit();rd.sync()
	var data:=rd.texture_get_data(target,0).to_float32_array();var expected:=[1.2,2.4,3.,4.];var passed:=data.size()==4
	for channel in 4:passed=passed and is_finite(data[channel]) and absf(data[channel]-expected[channel])<.00001
	owned.reverse()
	for rid in owned:rd.free_rid(rid)
	rd.free()
	FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify({"pixels_passed":passed,"actual":Array(data),"expected":expected,"layouts_push_bytes":[16,0,8,0],"clean_log_required":true,"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),"probe_sha256":FileAccess.get_sha256(get_script().resource_path)},"\t"))
	if passed:print("COMPUTE_BARRIER_PIXELS_PASS; clean log is also required");quit()
	else:push_error("Compute barrier output differs");quit(4)
