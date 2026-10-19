extends SceneTree
## Editor CLI entry point for the node-based release-pack fixture.
func _initialize():start.call_deferred()

func start():
	var path:String=get_script().resource_path.get_base_dir().path_join("probe_threaded_shader_loading.gd")
	var fixture=load(path)
	if fixture==null:quit(2);return
	root.add_child(fixture.new())
