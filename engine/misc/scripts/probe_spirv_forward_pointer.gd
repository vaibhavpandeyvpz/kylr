extends SceneTree
## Execute recursive physical-buffer references with a specialization constant.
## The original SPIR-V must survive the optional optimizer's unsupported case.
var rd:RenderingDevice
var resources:Array[RID]=[]
var output:String
var failed:=false
var result:Dictionary={}
const SOURCE="""#version 450
#extension GL_EXT_buffer_reference : require
layout(local_size_x=1,local_size_y=1,local_size_z=1) in;
layout(buffer_reference,std430,buffer_reference_align=16) buffer Node;
layout(buffer_reference,std430,buffer_reference_align=16) buffer Node { Node next; uint value; };
layout(set=0,binding=0,std430) buffer Output { uint answer; } dst;
layout(set=0,binding=1,std430) readonly buffer HeadWords { uint words[]; } head_words;
layout(set=0,binding=2,std430) readonly buffer TailWords { uint words[]; } tail_words;
layout(push_constant,std430) uniform Params { Node head; } params;
layout(constant_id=0) const uint ADD=1u;
void main(){dst.answer=params.head.next.value+ADD+head_words.words[2]+tail_words.words[0];}
"""

func _initialize():run.call_deferred()

func render_call(callback:Callable):
	var done:=Semaphore.new()
	RenderingServer.call_on_render_thread(func():callback.call();done.post())
	done.wait()

func gpu_run():
	rd=RenderingServer.get_rendering_device()
	if rd==null or not rd.has_feature(RenderingDevice.SUPPORTS_BUFFER_DEVICE_ADDRESS):failed=true;return
	var source:=RDShaderSource.new();source.source_compute=SOURCE
	var spirv:=rd.shader_compile_spirv_from_source(source)
	if not spirv.compile_error_compute.is_empty():push_error(spirv.compile_error_compute);failed=true;return
	var bytes:PackedByteArray=spirv.bytecode_compute
	var offset:=20;var declarations:=0
	while offset<bytes.size():
		var instruction:=bytes.decode_u32(offset);var words:=instruction>>16
		if words==0 or offset+words*4>bytes.size():failed=true;return
		if instruction&0xffff==39:declarations+=1 # SPIR-V OpTypeForwardPointer.
		offset+=words*4
	if declarations==0:push_error("Fixture did not compile a forward-pointer declaration");failed=true;return
	var shader:=rd.shader_create_from_spirv(spirv);resources.append(shader)
	var constant:=RDPipelineSpecializationConstant.new();constant.constant_id=0;constant.value=2
	var pipeline:=rd.compute_pipeline_create(shader,[constant]);resources.append(pipeline)
	if not shader.is_valid() or not pipeline.is_valid():failed=true;return
	var tail_bytes:=PackedByteArray();tail_bytes.resize(16);tail_bytes.encode_u32(8,40)
	var tail:=rd.storage_buffer_create(16,tail_bytes,0,RenderingDevice.BUFFER_CREATION_DEVICE_ADDRESS_BIT);resources.append(tail)
	var head_bytes:=PackedByteArray();head_bytes.resize(16);head_bytes.encode_u64(0,rd.buffer_get_device_address(tail))
	var head:=rd.storage_buffer_create(16,head_bytes,0,RenderingDevice.BUFFER_CREATION_DEVICE_ADDRESS_BIT);resources.append(head)
	var zero:=PackedByteArray();zero.resize(4)
	var destination:=rd.storage_buffer_create(4,zero);resources.append(destination)
	# The descriptors also declare both physical-node reads to the RD graph,
	# so initial uploads are synchronized before the address-based traversal.
	var uniforms:Array[RDUniform]=[]
	for binding in 3:
		var uniform:=RDUniform.new();uniform.uniform_type=RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER;uniform.binding=binding
		uniform.add_id([destination,head,tail][binding]);uniforms.append(uniform)
	var set:=rd.uniform_set_create(uniforms,shader,0);resources.append(set)
	var constants:=PackedByteArray();constants.resize(8);constants.encode_u64(0,rd.buffer_get_device_address(head))
	var list:=rd.compute_list_begin()
	rd.compute_list_bind_compute_pipeline(list,pipeline);rd.compute_list_bind_uniform_set(list,set,0)
	rd.compute_list_set_push_constant(list,constants,constants.size());rd.compute_list_dispatch(list,1,1,1)
	rd.compute_list_end()
	var answer:=rd.buffer_get_data(destination).decode_u32(0)
	failed=answer!=42
	result={"answer":answer,"expected":42,"forward_pointer_declarations":declarations,"specialization_value":2}

func run():
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="):output=arg.trim_prefix("--output=")
	if output.is_empty():quit(2);return
	render_call(gpu_run)
	render_call(func():
		resources.reverse()
		for rid in resources:
			if rid.is_valid():rd.free_rid(rid))
	result.merge({"passed":not failed,"engine_sha256":FileAccess.get_sha256(OS.get_executable_path()),
		"probe_sha256":FileAccess.get_sha256(get_script().resource_path),"quality_accepted":false,"performance_accepted":false})
	FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify(result,"\t"))
	if failed:push_error("Forward-pointer shader contract failed");quit(7)
	else:print("FORWARD_POINTER_GPU_PASS answer=42");quit()
