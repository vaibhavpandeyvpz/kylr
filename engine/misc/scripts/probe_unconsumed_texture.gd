extends SceneTree
## Repeated uploads without a sampling draw must retain cross-frame ordering.
var texture: RID

func _initialize(): run.call_deferred()

func create_texture():
	var format := RDTextureFormat.new()
	format.width = 128
	format.height = 128
	format.format = RenderingDevice.DATA_FORMAT_R8G8B8A8_UNORM
	format.usage_bits = RenderingDevice.TEXTURE_USAGE_CAN_UPDATE_BIT | RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT
	texture = RenderingServer.get_rendering_device().texture_create(format, RDTextureView.new())

func update_texture(bytes: PackedByteArray):
	RenderingServer.get_rendering_device().texture_update(texture, 0, bytes)

func release_texture():
	RenderingServer.get_rendering_device().free_rid(texture)

func run():
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.call_on_render_thread(create_texture)
	await process_frame
	for frame in 128:
		var bytes := PackedByteArray()
		bytes.resize(128 * 128 * 4)
		bytes.fill(frame % 256)
		RenderingServer.call_on_render_thread(update_texture.bind(bytes))
		RenderingServer.force_draw(false, 1.0 / 60.0)
		await process_frame
	RenderingServer.call_on_render_thread(release_texture)
	for frame in 4: await process_frame
	print("UNCONSUMED_TEXTURE_COMPLETE frames=128")
	quit()
