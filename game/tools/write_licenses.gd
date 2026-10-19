extends SceneTree
func _initialize():
	var path := "res://build/windows/ENGINE-LICENSES.txt"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): path = argument.trim_prefix("--output=")
	var file := FileAccess.open(path,FileAccess.WRITE)
	if file == null:
		push_error("Cannot write engine licenses: " + path)
		quit(1)
		return
	file.store_string(Engine.get_license_text()+"\n\n")
	for name in Engine.get_license_info():
		file.store_string(name+"\n"+Engine.get_license_info()[name]+"\n\n")
	for component in Engine.get_copyright_info():
		file.store_string(str(component)+"\n\n")
	quit()
