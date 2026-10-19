extends CompositorEffect
## Reference-only weighted linear-HDR averaging before spatial resolve/tonemapping.
## A requested batch is consumed once; subsequent draws hold the accumulated mean.
var _mutex:=Mutex.new()
var _requested_weight:=0
var _reset_requested:=false
var _completed_weight:=0
var _completed_batches:=0
var _error:=""
var _released:=false
var _rd:RenderingDevice
var _shader:=RID()
var _pipeline:=RID()
var _average:=RID()
var _size:=Vector2i.ZERO
var _total_weight:=0

const SOURCE:="""#version 450
layout(local_size_x=8,local_size_y=8,local_size_z=1) in;
layout(rgba16f,set=0,binding=0) uniform image2D scene_color;
layout(rgba32f,set=0,binding=1) uniform image2D accumulated;
layout(push_constant,std430) uniform Params {ivec2 size; uint previous_weight; uint batch_weight;} params;
void main(){
 ivec2 pixel=ivec2(gl_GlobalInvocationID.xy);
 if(any(greaterThanEqual(pixel,params.size)))return;
 vec4 mean;
 if(params.batch_weight==0u){mean=imageLoad(accumulated,pixel);}
 else{
  vec4 sample_color=imageLoad(scene_color,pixel);
  mean=sample_color;
  if(params.previous_weight!=0u){
   vec3 previous=imageLoad(accumulated,pixel).rgb;
   mean.rgb=(previous*float(params.previous_weight)+sample_color.rgb*float(params.batch_weight))/float(params.previous_weight+params.batch_weight);
  }
  imageStore(accumulated,pixel,mean);
 }
 imageStore(scene_color,pixel,mean);
}
"""

func _init():
	effect_callback_type=CompositorEffect.EFFECT_CALLBACK_TYPE_POST_OPAQUE
	access_resolved_color=true

func begin_capture():
	_mutex.lock()
	_reset_requested=true;_requested_weight=0;_completed_weight=0;_completed_batches=0
	_mutex.unlock()

func arm(sample_weight:int):
	_mutex.lock()
	if sample_weight<=0 or _requested_weight!=0:
		_error="Invalid or overlapping HDR reference request"
	else:_requested_weight=sample_weight
	_mutex.unlock()

func stats()->Dictionary:
	_mutex.lock()
	var result:={"weight":_completed_weight,"batches":_completed_batches,"error":_error,"released":_released}
	_mutex.unlock()
	return result

func _fail(message:String)->bool:
	_mutex.lock();_error=message;_mutex.unlock()
	push_error(message)
	return false

## Rendering-thread operation, also exercised with owned textures by the GPU test.
func append_color(color:RID,size:Vector2i,sample_weight:int,restart:=false)->bool:
	if _rd==null:_rd=RenderingServer.get_rendering_device()
	if _rd==null or not _rd.texture_is_valid(color):return _fail("Missing HDR reference color texture")
	var format:=_rd.texture_get_format(color)
	if format.format!=RenderingDevice.DATA_FORMAT_R16G16B16A16_SFLOAT or format.width!=size.x or format.height!=size.y or not (format.usage_bits&RenderingDevice.TEXTURE_USAGE_STORAGE_BIT):
		return _fail("HDR reference requires a storage-capable RGBA16F color layer")
	if restart:_total_weight=0
	if sample_weight<0 or (_total_weight==0 and sample_weight==0):return _fail("Invalid HDR reference sample weight")
	if not _shader.is_valid():
		var source:=RDShaderSource.new();source.source_compute=SOURCE
		var spirv:=_rd.shader_compile_spirv_from_source(source)
		if not spirv.compile_error_compute.is_empty():return _fail(spirv.compile_error_compute)
		_shader=_rd.shader_create_from_spirv(spirv)
		_pipeline=_rd.compute_pipeline_create(_shader)
	if _size!=size:
		if _total_weight>0:return _fail("HDR reference resized without a capture reset")
		if _average.is_valid():_rd.free_rid(_average)
		var average_format:=RDTextureFormat.new()
		average_format.width=size.x;average_format.height=size.y
		average_format.format=RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT
		average_format.usage_bits=RenderingDevice.TEXTURE_USAGE_STORAGE_BIT
		_average=_rd.texture_create(average_format,RDTextureView.new())
		_size=size
	if not _average.is_valid() or not _pipeline.is_valid():return _fail("Cannot allocate HDR reference accumulator")
	var a:=RDUniform.new();a.uniform_type=RenderingDevice.UNIFORM_TYPE_IMAGE;a.binding=0;a.add_id(color)
	var b:=RDUniform.new();b.uniform_type=RenderingDevice.UNIFORM_TYPE_IMAGE;b.binding=1;b.add_id(_average)
	var uniforms:=_rd.uniform_set_create([a,b],_shader,0)
	var constants:=PackedInt32Array([size.x,size.y,_total_weight,sample_weight]).to_byte_array()
	var list:=_rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(list,_pipeline)
	_rd.compute_list_bind_uniform_set(list,uniforms,0)
	_rd.compute_list_set_push_constant(list,constants,constants.size())
	_rd.compute_list_dispatch(list,ceili(size.x/8.0),ceili(size.y/8.0),1)
	_rd.compute_list_end()
	_rd.free_rid(uniforms)
	_total_weight+=sample_weight
	_mutex.lock()
	_completed_weight=_total_weight
	if sample_weight>0:_completed_batches+=1
	_mutex.unlock()
	return true

func _render_callback(_type:int,data:RenderData):
	_mutex.lock()
	var reset:=_reset_requested;_reset_requested=false
	var weight:=_requested_weight;_requested_weight=0
	var released:=_released
	_mutex.unlock()
	if released:return
	if reset:_total_weight=0
	if _total_weight==0 and weight==0:return
	var buffers:RenderSceneBuffersRD=data.get_render_scene_buffers()
	if buffers.get_view_count()!=1:_fail("HDR reference multiview is unsupported");return
	append_color(buffers.get_color_layer(0),buffers.get_internal_size(),weight)

func release():
	enabled=false
	RenderingServer.call_on_render_thread(_release_on_render_thread)

func _release_on_render_thread():
	if _rd:
		for resource in [_average,_pipeline,_shader]:
			if resource.is_valid():_rd.free_rid(resource)
	_average=RID();_pipeline=RID();_shader=RID();_size=Vector2i.ZERO;_total_weight=0
	_mutex.lock();_released=true;_mutex.unlock()
