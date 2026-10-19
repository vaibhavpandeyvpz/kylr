extends SceneTree
## Repeated writes to hidden/unconsumed buffers must remain synchronized across
## frames, including initialization on a transfer worker. Requires Vulkan.
var buffer:RID
var valid:=true
var payload:=PackedByteArray()
var bulk_buffers:Array[RID]=[]

func _initialize():run.call_deferred()

func create_buffer():
	var rd:=RenderingServer.get_rendering_device()
	buffer=rd.storage_buffer_create(720,payload)
	valid=valid and buffer.is_valid()
	# Reuse upload workers before the buffer's first graph-tracked operation,
	# as happens while a large collection of meshes/materials is being loaded.
	var bulk:=PackedByteArray();bulk.resize(32768);bulk.fill(7)
	for index in OS.get_processor_count()*3:
		bulk_buffers.append(rd.storage_buffer_create(bulk.size(),bulk))
	valid=valid and rd.buffer_update(buffer,0,payload.size(),payload)==OK

func update_buffer(data:PackedByteArray):
	valid=valid and RenderingServer.get_rendering_device().buffer_update(buffer,0,data.size(),data)==OK

func read_and_free():
	var rd:=RenderingServer.get_rendering_device()
	valid=valid and rd.buffer_get_data(buffer)==payload
	rd.free_rid(buffer)
	for resource in bulk_buffers:rd.free_rid(resource)
	bulk_buffers.clear()

func run():
	create_timer(30).timeout.connect(func():push_error("Buffer upload probe timed out");quit(2))
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	# A changing canvas forces real frame submission; otherwise a blank
	# viewport can batch these uploads into one graph despite post-draw signals.
	var canvas:=ColorRect.new();canvas.size=Vector2(64,64);root.add_child(canvas)
	payload.resize(720);payload.fill(1)
	RenderingServer.call_on_render_thread(create_buffer)
	for frame in 128:
		canvas.color=Color(float(frame%2),.2,.3)
		await RenderingServer.frame_post_draw
		payload=payload.duplicate();payload.fill(frame+2)
		RenderingServer.call_on_render_thread(update_buffer.bind(payload))
	await RenderingServer.frame_post_draw
	RenderingServer.call_on_render_thread(read_and_free)
	for frame in 4:await process_frame
	if valid:print("BUFFER_UPLOAD_GPU_PASS frames=128 bytes=720");quit()
	else:push_error("Buffer upload readback failed");quit(3)
