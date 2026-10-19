extends SceneTree
## A hidden skeleton still receives pose uploads. Repeated COPY_TO usage must
## synchronize even when no skinning draw reads its buffer between frames.
func _initialize():run.call_deferred()

func run():
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var skeleton:=RenderingServer.skeleton_create()
	RenderingServer.skeleton_allocate_data(skeleton,15)
	for frame in 128:
		var pose:=Transform3D.IDENTITY
		pose.origin.x=float(frame)*.01
		RenderingServer.skeleton_bone_set_transform(skeleton,0,pose)
		RenderingServer.force_draw(false,1.0/60.0)
		await process_frame
	RenderingServer.free_rid(skeleton)
	for frame in 4:await process_frame
	print("UNCONSUMED_SKELETON_GPU_PASS frames=128 bones=15")
	quit()
