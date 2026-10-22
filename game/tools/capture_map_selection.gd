extends SceneTree
## Photograph the real setup screen without reading or saving player preferences.
var output := "res://reports/map-selection"
var app

func _initialize(): run.call_deferred()

func run():
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output=argument.trim_prefix("--output=")
	assert(output.begins_with("res://reports/") and not DirAccess.dir_exists_absolute(output),"Choose a fresh capture directory under reports")
	DirAccess.make_dir_recursive_absolute(output)
	create_timer(240).timeout.connect(func(): push_error("Map-selection capture timed out");quit(2))
	AudioServer.set_bus_mute(0,true)
	var prefs := Preferences.new(output.path_join("preferences.cfg"))
	prefs.values=Preferences.DEFAULTS.duplicate(true)
	prefs.values.merge(Preferences.QUALITY_PRESETS[2],true)
	prefs.values.quality=2
	prefs.values.quality_benchmarked=true
	prefs.values.resolution=Vector2i(1920,1080)
	prefs.values.display_mode=1
	prefs.values.name="Pilot"
	prefs.values.reduced_motion=true
	prefs.save()
	app=load("res://app.tscn").instantiate()
	app.set_meta("preferences_path",prefs.storage_path)
	app.set_meta("automated_profile",true)
	root.add_child(app)
	await process_frame
	if not app.startup_complete: await app.startup_finished
	for map in MapCatalog.all():
		app.prefs.values.map=map.id
		app.ui.setup()
		for node in app.ui.page.find_children("*","",true,false):
			if node is MapPreview:
				node.set_process(false)
				node.show_slide(0)
		for frame in 30: await RenderingServer.frame_post_draw
		assert(root.size==Vector2i(1920,1080))
		assert(root.get_texture().get_image().save_png(output.path_join(map.id+".png"))==OK)
		print("MAP_SELECTION_CAPTURE ",map.id," native 1920x1080")
	await app.request_quit()
