extends SceneTree
## Diagnostic source pack for the optimized runtime; not a shipping export.
## Keeps profiler scripts and import caches, without modifying project/presets.

var packer := PCKPacker.new()
var output := "res://reports/performance/release-diagnostic"
var count := 0
var failed := false
var verify_only := ""

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):output=argument.trim_prefix("--output=")
		if argument.begins_with("--verify-only="):verify_only=argument.trim_prefix("--verify-only=")
		if argument.begins_with("--expected-files="):count=int(argument.trim_prefix("--expected-files="))
	call_deferred("run" if verify_only.is_empty() else "run_verification")

static func verify_pack(path: String, expected_files: int) -> bool:
	# A successful PCKPacker.flush() and a matching whole-file hash do not
	# establish completeness after a disk-full write. Check the directory and
	# every payload against its stored digest before using the package.
	var file := FileAccess.open(path,FileAccess.READ)
	if file==null or expected_files<1 or file.get_length()<104:return false
	if file.get_32()!=0x43504447 or file.get_32()!=4:return false
	file.seek(20)
	if file.get_32()!=2:return false # This tool writes unencrypted relative-base PCKs.
	var base:=file.get_64()
	var directory:=file.get_64()
	if base<104 or directory<base or directory+4>file.get_length():return false
	file.seek(directory)
	if file.get_32()!=expected_files:return false
	var entries:Array[Dictionary]=[]
	var paths:Dictionary={}
	for index in expected_files:
		if file.get_position()+4>file.get_length():return false
		var path_length:=file.get_32()
		if path_length<1 or path_length>16384 or file.get_position()+path_length+36>file.get_length():return false
		var entry_path:=file.get_buffer(path_length).get_string_from_utf8()
		var offset:=file.get_64()
		var size:=file.get_64()
		var digest:=file.get_buffer(16)
		if file.get_32()!=0 or offset>directory-base or size>directory-base-offset:return false
		if paths.has(entry_path):return false
		paths[entry_path]=true
		entries.append({"offset":base+offset,"size":size,"digest":digest})
	if not paths.has("project.godot") or not paths.has("rendered_profile.tscn") or not paths.has("scripts/debug/rendered_combat_profile.gd"):return false
	for entry in entries:
		file.seek(entry.offset)
		var hash:=HashingContext.new()
		if hash.start(HashingContext.HASH_MD5)!=OK:return false
		var remaining:int=entry.size
		while remaining>0:
			var bytes:=file.get_buffer(mini(remaining,1048576))
			if bytes.is_empty() or hash.update(bytes)!=OK:return false
			remaining-=bytes.size()
		if hash.finish()!=entry.digest:return false
	return true

func run_verification() -> void:
	var valid:=verify_pack(verify_only,count)
	print("RENDERED_DIAGNOSTIC_PACK_VERIFIED valid=",valid," files=",count)
	quit(0 if valid else 3)

func add_file(resource_path: String, source_path := "") -> void:
	if failed: return
	if source_path.is_empty(): source_path = resource_path
	var error := packer.add_file(resource_path, source_path)
	if error != OK:
		push_error("Cannot pack %s: %s" % [resource_path, error_string(error)])
		failed = true
		return
	count += 1

func add_directory(path: String) -> void:
	if failed: return
	var directory := DirAccess.open(path)
	if directory == null:
		push_error("Missing pack input: " + path)
		failed = true
		return
	for child in directory.get_directories():
		if not child.begins_with("."): add_directory(path.path_join(child))
	for child in directory.get_files():
		if child.ends_with(".dll") or child.ends_with(".so") or child.ends_with(".dylib"): continue
		add_file(path.path_join(child))

func run() -> void:
	var destination := ProjectSettings.globalize_path(output)
	if DirAccess.dir_exists_absolute(destination):
		push_error("Choose a fresh diagnostic runtime directory; preserve earlier packages")
		quit(1);return
	if DirAccess.make_dir_recursive_absolute(destination)!=OK:quit(1);return
	var runtime := OS.get_environment("GODOT_TEMPLATE")
	if runtime.is_empty(): runtime=OS.get_data_dir().path_join("Godot/export_templates/4.7.2.stable/windows_release_x86_64.exe")
	if not FileAccess.file_exists(runtime) or DirAccess.copy_absolute(runtime,destination.path_join("KylrDiagnostic.exe")) != OK:
		push_error("Install the official Windows release template or set GODOT_TEMPLATE")
		quit(1);return
	# Native extensions must be real files beside the PCK. An existing staging
	# directory must not hide missing dependencies in a newly created pack.
	var extension_directory:=destination.path_join("addons/limboai/bin")
	if DirAccess.make_dir_recursive_absolute(extension_directory)!=OK:quit(1);return
	var extension:="liblimboai.windows.template_release.x86_64.dll"
	if DirAccess.copy_absolute(ProjectSettings.globalize_path("res://addons/limboai/bin/"+extension),extension_directory.path_join(extension))!=OK:
		push_error("Cannot stage the release native extension");quit(1);return
	var config := ConfigFile.new()
	if config.load("res://project.godot") != OK:
		push_error("Cannot read project settings")
		quit(1)
		return
	config.set_value("application", "run/main_scene", "res://rendered_profile.tscn")
	var settings_path := output.path_join("diagnostic-project.godot")
	config.save(settings_path)
	var scene_path := output.path_join("diagnostic-main.tscn")
	var scene := FileAccess.open(scene_path, FileAccess.WRITE)
	scene.store_string('[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://scripts/debug/rendered_combat_profile.gd" id="1"]\n\n[node name="RenderedCombatProfile" type="Node"]\nscript = ExtResource("1")\n')
	scene.close()
	var error := packer.pck_start(output.path_join("KylrDiagnostic.pck"))
	if error != OK:
		push_error("Cannot create diagnostic pack: " + error_string(error))
		quit(1)
		return
	add_file("res://project.godot", settings_path)
	add_file("res://rendered_profile.tscn", scene_path)
	for directory in ["assets", "addons", "scripts", "shaders", "data", ".godot/imported"]:
		add_directory("res://" + directory)
	for path in ["main.tscn", "app.tscn", "icon.svg", ".godot/global_script_class_cache.cfg", ".godot/extension_list.cfg", ".godot/uid_cache.bin"]:
		add_file("res://" + path)
	for path in DirAccess.get_files_at("res://"):
		if path.ends_with(".tres") or path.ends_with(".res"): add_file("res://" + path)
	if failed:
		quit(2)
		return
	error = packer.flush()
	if error != OK:
		push_error("Cannot finalize diagnostic pack: " + error_string(error))
		quit(1)
		return
	if not verify_pack(output.path_join("KylrDiagnostic.pck"),count):
		push_error("Diagnostic pack failed directory/payload verification; do not run it")
		quit(3)
		return
	print("RENDERED_DIAGNOSTIC_PACK_READY files=", count, " path=", output)
	FileAccess.open(output.path_join("manifest.json"),FileAccess.WRITE).store_string(JSON.stringify({
		"diagnostic_only":true,"files":count,
		"engine_sha256":FileAccess.get_sha256(runtime),
		"pack_sha256":FileAccess.get_sha256(output.path_join("KylrDiagnostic.pck")),
		"pack_content_verified":true,"verified_payloads":count,
		"profile_sha256":FileAccess.get_sha256("res://scripts/debug/rendered_combat_profile.gd"),
		"production_quality_accepted":false},"\t"))
	quit()
