extends SceneTree
## Sample live combustion impacts from several views in the assembled arena.
const Preparation = preload("res://scripts/core/resource_preparation.gd")
const Observer = preload("res://scripts/debug/reconstruction_observer.gd")

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	root.size = Vector2i(1280,720)
	var rt := OS.get_cmdline_user_args().has("--rt")
	var kind := "fire_hit" if OS.get_cmdline_user_args().has("--fireball") else "grenade" if OS.get_cmdline_user_args().has("--grenade") else "rocket"
	var view_scale := 0.35 if kind=="fire_hit" else 1.0
	var mode := "rt" if rt else "raster"
	var folder := "res://reports/"+kind+"-3d/"+mode+"/"
	DirAccess.make_dir_recursive_absolute(folder)
	var game := ArenaMatch.new()
	game.online = true
	game.map_id = "faceoff"
	root.add_child(game)
	for frame in 4: await physics_frame
	game.map.start_map_assembly()
	game.map.assembly.seek(5,true)
	game.map.assembly.pause()
	game.map.start_loadout()
	game.set_process(false)
	game.set_physics_process(false)
	game.camera_rig.queue_free()
	await process_frame
	var prefs := Preferences.new("res://reports/rocket_preview_unused.cfg")
	prefs.values.quality = 3
	for key in Preferences.QUALITY_PRESETS[3]: prefs.values[key] = Preferences.QUALITY_PRESETS[3][key]
	prefs.values.ray_tracing = rt
	prefs.apply_rendering(game)
	var camera := Camera3D.new()
	game.add_child(camera)
	game.camera = camera
	camera.current = true
	var contact := game.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(19,40,-12),Vector3(19,-10,-12),1))
	assert(not contact.is_empty() and contact.normal.y>0.7)
	var anchor: Vector3 = contact.position+contact.normal*0.025
	camera.position = anchor+Vector3(3,1.8,5)*view_scale
	camera.look_at(anchor+Vector3.UP*0.8*view_scale)
	var observer: CompositorEffect
	if rt:
		var world: WorldEnvironment = game.find_children("*","WorldEnvironment",true,false)[0]
		world.compositor = Compositor.new()
		observer = Observer.new()
		world.compositor.compositor_effects = [observer]
		var ready: Dictionary = await Preparation.wait_for_rendering(self,root,true)
		if not ready.ready:
			push_error(str(ready))
			quit(2)
			return
	var burst := load("res://assets/effects/original/"+kind+".tscn").instantiate() as OriginalEffect
	game.add_child(burst)
	burst.position = anchor
	burst.play()
	burst.set_process(false)
	for emitter in burst.emitters: emitter.emitting = false
	for frame in 60: await process_frame
	for phase in [0.03,0.08,0.18,0.36,0.6,0.85]:
		await capture(burst,phase,folder+"phase-"+str(roundi(phase*100))+".png")
	for view in [{"name":"side","eye":Vector3(-4,1.6,2)}, {"name":"back","eye":Vector3(0,2,-5)}, {"name":"above","eye":Vector3(1,5,1)}]:
		camera.position = anchor+view.eye*view_scale
		camera.look_at(anchor+Vector3.UP*0.8*view_scale)
		await capture(burst,0.18,folder+view.name+".png")
	camera.position = anchor+Vector3(3,1.8,5)*view_scale
	camera.look_at(anchor+Vector3.UP*0.8*view_scale)
	burst.set_detail(0)
	await capture(burst,0.18,folder+"low.png")
	burst.set_detail(3)
	# Foreground fixture covers the whole cloud. Gas must respect opaque depth.
	var shield := MeshInstance3D.new()
	shield.mesh = BoxMesh.new()
	shield.mesh.size = Vector3(4,4,0.2)
	game.add_child(shield)
	shield.position = anchor+Vector3(1.5,0.9,2.5)
	shield.look_at(camera.position)
	await capture(burst,0.18,folder+"occluded.png")
	shield.queue_free()
	await process_frame
	camera.position = anchor+Vector3(0,0.7,0.15)*view_scale
	camera.look_at(anchor+Vector3.UP*0.8*view_scale)
	await capture(burst,0.18,folder+"inside.png")
	camera.position = anchor+Vector3(3,1.8,5)*view_scale
	camera.look_at(anchor+Vector3.UP*0.8*view_scale)
	# Surface orientation also exercises a side impact without camera-facing cards.
	burst.basis = Basis(Vector3.FORWARD,PI/2)
	await capture(burst,0.18,folder+"wall-axis.png")
	if OS.get_cmdline_user_args().has("--motion"):
		burst.basis = Basis.IDENTITY
		DirAccess.make_dir_recursive_absolute(folder+"motion")
		burst.play()
		for frame in 100:
			await process_frame
			await RenderingServer.frame_post_draw
			assert(root.get_texture().get_image().save_png(folder+"motion/%03d.png"%frame)==OK)
	if observer:
		var stats: Dictionary = observer.call("stats")
		print("ROCKET_PREVIEW_NATIVE ",JSON.stringify(stats))
		assert(stats.frames>0 and stats.error.is_empty() and stats.adapter.get("evaluation_succeeded",false))
		observer.call("release")
	print("COMBUSTION_3D_PREVIEW_PASS ",kind," ",mode," gpu=",RenderingServer.get_video_adapter_name())
	game.queue_free()
	for frame in 4: await process_frame
	quit()

func capture(burst: OriginalEffect, phase: float, path: String) -> void:
	burst.age = burst.duration*phase
	burst._process(0)
	burst.set_process(false)
	for frame in 20: await process_frame
	await RenderingServer.frame_post_draw
	assert(root.get_texture().get_image().save_png(path)==OK)
