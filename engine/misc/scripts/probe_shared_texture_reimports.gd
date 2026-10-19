@tool
extends EditorPlugin
## Editor-only scheduling regression: duplicate image paths and UID aliases.
var events: Array = []

func _enter_tree():
	get_tree().create_timer(2).timeout.connect(run)
	get_tree().create_timer(60).timeout.connect(func():
		push_error("SHARED_TEXTURE_REIMPORT_TIMEOUT")
		get_tree().quit(9))

func run():
	var filesystem := EditorInterface.get_resource_filesystem()
	while filesystem.is_scanning(): await get_tree().process_frame
	filesystem.resources_reimported.connect(func(files: PackedStringArray): events.append(Array(files)))
	var uid := ResourceLoader.get_resource_uid("res://shared.png")
	if uid == ResourceUID.INVALID_ID:
		push_error("Shared fixture image was not imported")
		get_tree().quit(2)
		return
	var cases: Array = []
	for use_alias in [false, true]:
		events.clear()
		var requests := PackedStringArray()
		for i in 64:
			if use_alias and i % 3 == 0: requests.append("res://second.png")
			elif use_alias and i % 3 == 1: requests.append(ResourceUID.id_to_text(uid))
			else: requests.append("res://shared.png")
		filesystem.reimport_files(requests)
		var expected := ["res://second.png", "res://shared.png"] if use_alias else ["res://shared.png"]
		var actual: Array = events[0].duplicate() if events.size() == 1 else []
		actual.sort()
		cases.append({"uid_aliases": use_alias, "requests": requests.size(),
			"events": events.duplicate(true), "passed": events.size() == 1 and actual == expected})
	var images: Array = []
	for name in ["shared", "second"]:
		var texture: Texture2D = ResourceLoader.load("res://" + name + ".png", "Texture2D", ResourceLoader.CACHE_MODE_REPLACE)
		var image := texture.get_image() if texture else null
		var expected := Color8(40, 80, 120) if name == "shared" else Color8(160, 100, 20)
		var valid: bool = image != null and image.get_size() == Vector2i(16, 16)
		if valid:
			var color: Color = image.get_pixel(8, 8)
			valid = absf(color.r - expected.r) < 1.0 / 255.0 and absf(color.g - expected.g) < 1.0 / 255.0 and absf(color.b - expected.b) < 1.0 / 255.0
		images.append({"name": name, "passed": valid})
	var threaded: bool = ProjectSettings.get_setting("editor/import/use_multiple_threads", false)
	var passed: bool = threaded and cases.all(func(row): return row.passed) and images.all(func(row): return row.passed)
	var report := {"passed": passed, "cases": cases, "images": images, "threaded_import": threaded,
		"engine_sha256": FileAccess.get_sha256(OS.get_executable_path()), "gpu_test": false}
	FileAccess.open("res://result.json", FileAccess.WRITE).store_string(JSON.stringify(report, "\t"))
	print("SHARED_TEXTURE_REIMPORT_PASS" if passed else "SHARED_TEXTURE_REIMPORT_FAIL")
	get_tree().quit(0 if passed else 1)
