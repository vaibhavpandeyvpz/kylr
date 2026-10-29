@tool
extends EditorPlugin
var exporter: EditorExportPlugin

func _enter_tree() -> void:
	if OS.get_environment("KYLR_ANDROID_EXPORT")=="1":
		var settings:=EditorInterface.get_editor_settings()
		settings.set_setting("export/android/android_sdk_path",OS.get_environment("ANDROID_HOME"))
		settings.set_setting("export/android/java_sdk_path",OS.get_environment("JAVA_HOME"))
	exporter=preload("res://addons/kylr_export/mesh_lod_export.gd").new()
	add_export_plugin(exporter)

func _exit_tree() -> void:
	remove_export_plugin(exporter)
