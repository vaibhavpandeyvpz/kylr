extends SceneTree
## Render the capture footprint and verify Reduced Motion freezes both teams.
func _initialize() -> void: run.call_deferred()

func run() -> void:
	root.size = Vector2i(1000,600)
	var stage := Node3D.new()
	root.add_child(stage)
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR
	world.environment.background_color = Color("101822")
	world.environment.glow_enabled = true
	stage.add_child(world)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.position = Vector3(0,4,4)
	camera.look_at(Vector3.ZERO)
	camera.current = true
	var pads: Array[FlagBaseEffect] = []
	for index in 2:
		var pad := FlagBaseEffect.new()
		pad.configure(Color("30bfff") if index == 0 else Color("ff4938"),false)
		stage.add_child(pad)
		pad.position.x = -1.3 if index == 0 else 1.3
		pads.append(pad)
	await create_timer(1.0).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://reports/original-fields.png")
	for pad in pads: pad.configure(pad.last_color,true)
	for frame in 12: await process_frame
	await RenderingServer.frame_post_draw
	var frozen := root.get_texture().get_image()
	for frame in 30: await process_frame
	await RenderingServer.frame_post_draw
	var still := root.get_texture().get_image()
	var difference := 0.0
	for y in frozen.get_height():
		for x in frozen.get_width():
			var delta := frozen.get_pixel(x,y)-still.get_pixel(x,y)
			difference = maxf(difference,maxf(absf(delta.r),maxf(absf(delta.g),absf(delta.b))))
	print("ORIGINAL_FIELDS reduced_motion_error=",difference)
	stage.queue_free()
	await process_frame
	quit(0 if difference <= 1.0/255.0 else 1)
