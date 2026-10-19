extends GutTest

func test_render_thread_defaults_off_in_every_quality_preset():
	assert_false(Preferences.DEFAULTS.separate_rendering_thread)
	for preset in Preferences.QUALITY_PRESETS:
		var settings:=Preferences.DEFAULTS.duplicate(true)
		settings.merge(preset,true)
		assert_false(settings.separate_rendering_thread)

func test_render_thread_setting_round_trip_and_early_engine_override():
	var path:="user://render_thread_preferences_test.cfg"
	var startup_path:="user://render_thread_startup_test.cfg"
	var prefs:=Preferences.new(path)
	for enabled in [true,false]:
		prefs.values.separate_rendering_thread=enabled
		assert_eq(prefs.save(),OK)
		var restored:=Preferences.new(path)
		assert_eq(restored.values.separate_rendering_thread,enabled)
		assert_eq(restored.save_rendering_startup(startup_path),OK)
		var config:=ConfigFile.new()
		assert_eq(config.load(startup_path),OK)
		assert_eq(config.get_value("rendering","driver/threads/thread_model"),2 if enabled else 1)
	DirAccess.remove_absolute(path)
	DirAccess.remove_absolute(startup_path)
