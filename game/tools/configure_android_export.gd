@tool
extends SceneTree

func _initialize() -> void:
	configure.call_deferred()

func configure() -> void:
	var sdk:=OS.get_environment("ANDROID_HOME")
	var java:=OS.get_environment("JAVA_HOME")
	if not DirAccess.dir_exists_absolute(sdk) or not DirAccess.dir_exists_absolute(java):
		push_error("ANDROID_HOME and JAVA_HOME must identify installed SDKs")
		quit(1)
		return
	var presets:=ConfigFile.new()
	if presets.load("res://export_presets.cfg")!=OK:
		quit(1)
		return
	var found:=false
	for section in presets.get_sections():
		if presets.get_value(section,"name","")!="Android Release": continue
		presets.set_value(section+".options","version/name",OS.get_environment("KYLR_ANDROID_VERSION_NAME"))
		presets.set_value(section+".options","version/code",int(OS.get_environment("KYLR_ANDROID_VERSION_CODE")))
		found=true
	if not found or presets.save("res://export_presets.cfg")!=OK:
		push_error("Cannot configure Android Release export preset")
		quit(1)
		return
	quit()
