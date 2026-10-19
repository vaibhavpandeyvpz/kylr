extends GutTest

func test_backend_selection_requires_supported_dlss():
	assert_eq(Preferences.resolve_rt_denoiser(Preferences.DENOISER_DLSS,{"dlss":false}),-1)
	assert_eq(Preferences.resolve_rt_denoiser(Preferences.DENOISER_DLSS,{"dlss":true}),Preferences.DENOISER_DLSS)
	for removed_choice in [1,2,3,99]:
		assert_eq(Preferences.resolve_rt_denoiser(removed_choice,{"dlss":true}),-1)

func test_ultra_uses_dlss():
	assert_eq(Preferences.DEFAULTS.rt_denoiser,Preferences.DENOISER_DLSS)
	assert_eq(Preferences.QUALITY_PRESETS[3].rt_denoiser,Preferences.DENOISER_DLSS)

func test_upscaling_choice_survives_reload():
	var path:="user://test_rt_denoiser_preferences.cfg"
	var prefs:=Preferences.new(path)
	prefs.values.rt_upscaling=false
	assert_eq(prefs.save(),OK)
	var restored:=Preferences.new(path)
	assert_eq(restored.values.rt_denoiser,Preferences.DENOISER_DLSS)
	assert_false(restored.values.rt_upscaling)
	DirAccess.remove_absolute(path)

func test_removed_and_invalid_saved_modes_migrate_to_dlss():
	var path:="user://test_rt_denoiser_invalid.cfg"
	var config:=ConfigFile.new()
	for choice in [-1,1,2,3,99]:
		config.set_value("preferences","rt_denoiser",choice)
		assert_eq(config.save(path),OK)
		var prefs:=Preferences.new(path)
		assert_eq(prefs.values.rt_denoiser,Preferences.DENOISER_DLSS)
	DirAccess.remove_absolute(path)
