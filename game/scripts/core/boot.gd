extends Node
const LoadingScreen=preload("res://scripts/ui/loading_screen.gd")

func _ready() -> void:
	var loading := LoadingScreen.new()
	add_child(loading)
	await loading.paint()
	var path := "res://app.tscn"
	var packed: PackedScene
	if DisplayServer.get_name()=="headless":
		# Match the resource preparation path: dummy mesh RIDs are not safe for
		# concurrent creation from script/scene dependencies on loader workers.
		packed=load(path)
	else:
		var request := ResourceLoader.load_threaded_request(path,"PackedScene")
		if request!=OK:
			push_error("Application loading failed: "+error_string(request))
			get_tree().quit(1)
			return
		while ResourceLoader.load_threaded_get_status(path)==ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			await get_tree().process_frame
		if ResourceLoader.load_threaded_get_status(path)!=ResourceLoader.THREAD_LOAD_LOADED:
			push_error("Application scene failed to load")
			get_tree().quit(1)
			return
		packed=ResourceLoader.load_threaded_get(path) as PackedScene
	var app := packed.instantiate()
	# Automated startup runs can isolate preferences before App._ready(), while
	# exercising the same loading/scene handoff as a normal launch.
	for key in ["preferences_path", "automated_profile"]:
		if has_meta(key): app.set_meta(key, get_meta(key))
	loading.reparent(get_tree().root)
	app.set_meta("startup_loading_screen",loading)
	get_tree().root.add_child(app)
	get_tree().current_scene=app
	queue_free()
