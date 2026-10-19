extends RefCounted
## Quality-harness snapshots: copy rendered viewport frames on the GPU and
## defer CPU readback/PNG encoding until the motion sequence has finished.
## This is diagnostic storage, not a runtime recording or FPS feature.
const MAX_BYTES=1024*1024*1024
var _mutex:=Mutex.new()
var _rd:RenderingDevice
var _texture:=RID()
var _slots:Array[RID]=[]
var _written:Array[bool]=[]
var _buffers:Array[PackedByteArray]=[]
var _size:=Vector2i.ZERO
var _format:=0
var _image_format:=Image.FORMAT_RGBA8
var _ready:=false
var _readback_ready:=false
var _released:=false
var _error:=""
var _copied:=0
var _bytes:=0
var _slot_count:=0

func prepare(texture:RID,count:int):
	RenderingServer.call_on_render_thread(_prepare.bind(texture,count))

func capture(index:int):
	RenderingServer.call_on_render_thread(_capture.bind(index))

func readback():
	RenderingServer.call_on_render_thread(_readback)

func release():
	RenderingServer.call_on_render_thread(_release)

func stats()->Dictionary:
	_mutex.lock()
	var result:={"ready":_ready,"readback_ready":_readback_ready,"released":_released,"error":_error,"copied":_copied,"slots":_slot_count,"size":_size,"format":_format,"bytes":_bytes}
	_mutex.unlock();return result

func images()->Array[Image]:
	_mutex.lock()
	var buffers:=_buffers.duplicate();var dimensions:=_size;var format:=_image_format;var ready:=_readback_ready
	_mutex.unlock()
	var result:Array[Image]=[]
	if not ready:return result
	for bytes in buffers:result.append(Image.create_from_data(dimensions.x,dimensions.y,false,format,bytes))
	return result

func _fail(message:String):
	_mutex.lock();_error=message;_mutex.unlock();push_error(message)

func _prepare(texture:RID,count:int):
	if _released or not _slots.is_empty() or count<=0 or count>128:_fail("Invalid or repeated GPU frame-capture preparation");return
	_rd=RenderingServer.get_rendering_device();_texture=texture
	if _rd==null:_fail("GPU frame capture requires RenderingDevice");return
	var source:=RenderingServer.texture_get_rd_texture(texture)
	if not _rd.texture_is_valid(source):_fail("Missing viewport capture texture");return
	var format:=_rd.texture_get_format(source)
	var bytes_per_pixel:=4
	if format.format==RenderingDevice.DATA_FORMAT_R16G16B16A16_SFLOAT:_image_format=Image.FORMAT_RGBAH;bytes_per_pixel=8
	elif format.format not in [RenderingDevice.DATA_FORMAT_R8G8B8A8_UNORM,RenderingDevice.DATA_FORMAT_R8G8B8A8_SRGB]:_fail("Unsupported viewport capture format");return
	if format.texture_type!=RenderingDevice.TEXTURE_TYPE_2D or format.array_layers!=1 or format.samples!=RenderingDevice.TEXTURE_SAMPLES_1 or not (format.usage_bits&RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT):
		_fail("Viewport capture texture must be a copyable single-view color texture");return
	var bytes:=format.width*format.height*bytes_per_pixel*count
	if bytes>MAX_BYTES:_fail("GPU quality capture exceeds its 1 GiB storage limit");return
	_mutex.lock();_bytes=bytes;_size=Vector2i(format.width,format.height);_format=format.format;_mutex.unlock()
	var destination:=RDTextureFormat.new();destination.width=_size.x;destination.height=_size.y;destination.format=_format
	# RenderingDevice creates image views, which require a non-transfer usage.
	destination.usage_bits=RenderingDevice.TEXTURE_USAGE_CAN_COPY_TO_BIT|RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT|RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT
	for index in count:
		var slot:=_rd.texture_create(destination,RDTextureView.new())
		if not slot.is_valid():_fail("Cannot allocate GPU quality-capture storage");return
		_slots.append(slot);_written.append(false)
	_mutex.lock();_slot_count=count;_ready=true;_mutex.unlock()

func _capture(index:int):
	if not _ready or _released or not _error.is_empty() or index<0 or index>=_slots.size() or _written[index]:_fail("Invalid GPU frame-capture request");return
	var source:=RenderingServer.texture_get_rd_texture(_texture)
	if not _rd.texture_is_valid(source):_fail("Viewport capture source disappeared");return
	var format:=_rd.texture_get_format(source)
	if Vector2i(format.width,format.height)!=_size or format.format!=_format:_fail("Viewport changed during GPU motion capture");return
	if _rd.texture_copy(source,_slots[index],Vector3.ZERO,Vector3.ZERO,Vector3(_size.x,_size.y,1),0,0,0,0)!=OK:
		_fail("GPU viewport snapshot failed");return
	_written[index]=true
	_mutex.lock();_copied+=1;_mutex.unlock()

func _readback():
	if not _ready or _released or _copied!=_slots.size() or not _error.is_empty():_fail("Incomplete GPU frame sequence");return
	var buffers:Array[PackedByteArray]=[]
	for texture in _slots:
		var bytes:=_rd.texture_get_data(texture,0)
		if bytes.is_empty():_fail("GPU frame snapshot readback failed");return
		buffers.append(bytes)
	_mutex.lock();_buffers=buffers;_readback_ready=true;_mutex.unlock()

func _release():
	if _released:return
	if _rd:
		for texture in _slots:_rd.free_rid(texture)
	_mutex.lock();_slots.clear();_written.clear();_buffers.clear();_slot_count=0;_released=true;_ready=false;_readback_ready=false;_mutex.unlock()
