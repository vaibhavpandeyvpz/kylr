extends SceneTree
## Pack an asset-free fixture for templates with path overrides disabled.
func _initialize():
	var output:="";var project:="";var probe:="";var loop_class:="RTUnshadedFixture"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):output=argument.trim_prefix("--output=")
		if argument.begins_with("--project="):project=argument.trim_prefix("--project=")
		if argument.begins_with("--probe="):probe=argument.trim_prefix("--probe=")
		if argument.begins_with("--loop-class="):loop_class=argument.trim_prefix("--loop-class=")
	if output.is_empty() or project.is_empty() or probe.is_empty() or not loop_class.is_valid_identifier() or FileAccess.file_exists(output):quit(2);return
	var config:=ConfigFile.new()
	if config.load(project)!=OK:quit(2);return
	config.set_value("application","run/main_loop_type",loop_class)
	# Release startup validates a main scene before instantiating a custom loop.
	config.set_value("application","run/main_scene","res://fixture.tscn")
	var packed_config:=output+".project.godot"
	if config.save(packed_config)!=OK:quit(2);return
	var classes:=ConfigFile.new()
	classes.set_value("","list",[{"base":&"SceneTree","class":StringName(loop_class),"icon":"","language":&"GDScript","path":"res://probe.gd","is_abstract":false,"is_tool":false}])
	var cache:=output+".classes.cfg"
	if classes.save(cache)!=OK:quit(2);return
	var packer:=PCKPacker.new()
	if packer.pck_start(output)!=OK:quit(2);return
	var scene:=output+".tscn"
	var scene_file:=FileAccess.open(scene,FileAccess.WRITE)
	if scene_file==null:quit(3);return
	scene_file.store_string('[gd_scene format=3]\n\n[node name="Fixture" type="Node"]\n')
	scene_file.close()
	if packer.add_file("res://fixture.tscn",scene)!=OK:quit(3);return
	for file in [["res://project.godot",packed_config],["res://probe.gd",probe],["res://.godot/global_script_class_cache.cfg",cache]]:
		if packer.add_file(file[0],file[1])!=OK:quit(3);return
	if packer.flush()!=OK:quit(3);return
	print("RT_UNSHADED_PACK_READY")
	quit()
