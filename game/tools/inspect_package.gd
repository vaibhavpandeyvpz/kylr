extends SceneTree
## Mount after startup in an empty project: -- --pack=<absolute PCK>.
## This inspects package contents without selecting editor-only native libraries.
var files := 0
var failed := false

func _initialize():
	var pack:=""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--pack="):pack=argument.trim_prefix("--pack=")
	if pack.is_empty() or not ProjectSettings.load_resource_pack(pack):
		push_error("Cannot mount package for inspection");quit(2);return
	inspect("res://")
	for path in ["res://data/audio/speech.json","res://data/audio/music.json","res://assets/audio/music/lobby.ogg","res://assets/audio/speech/robot_09/power_critical.wav"]:
		if not ResourceLoader.exists(path): reject("Missing packaged resource: "+path)
	var animations: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/animations/manifest.json"))
	for entry in animations.values():
		for field in ["file","weapon_file"]:
			if entry.has(field): require_resource("res://assets/animations/"+String(entry[field]))
	var audio: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/audio/catalog.json"))
	for entry in audio.values():
		if entry.has("file"): require_resource(String(entry.file))
		for path in entry.get("files",[]): require_resource(String(path))
	print("PACKAGE_INSPECTION files=",files," safe=",not failed)
	quit(1 if failed else 0)

func reject(message: String):
	failed = true
	push_error(message)

func require_resource(path: String) -> void:
	if not ResourceLoader.exists(path): reject("Missing catalog resource: "+path)

func inspect(path: String):
	var folder := DirAccess.open(path)
	if folder == null: reject("Unreadable package folder: "+path); return
	for child in folder.get_directories():
		var next := path.path_join(child)
		if next in ["res://services","res://reports","res://tests","res://tools","res://docs","res://.codex","res://.claude","res://addons/gut","res://scripts/debug"]: reject("Excluded source directory packaged: "+next)
		inspect(next)
	for child in folder.get_files():
		files += 1
		if child == ".env" or child.begins_with(".env."): reject("Environment configuration packaged: "+path.path_join(child))
