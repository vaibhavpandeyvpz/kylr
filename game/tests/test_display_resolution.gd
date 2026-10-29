extends GutTest

func test_platform_defaults_and_phone_choices_follow_native_aspect():
	assert_eq(Preferences.default_resolution(Vector2i(2400,1080),true),Vector2i(1600,720))
	assert_eq(Preferences.default_resolution(Vector2i(2560,1440),false),Vector2i(2560,1440))
	assert_eq(Preferences.default_resolution(Vector2i(960,540),true),Vector2i(960,540))
	var choices:=Preferences.resolutions(Vector2i(2400,1080),true)
	assert_has(choices,Vector2i(1600,720))
	assert_has(choices,Vector2i(2400,1080))
	for choice in choices: assert_almost_eq(float(choice.x)/choice.y,2400.0/1080,0.003)

func test_aspect_fit_centers_content_without_stretching():
	assert_eq(Preferences.effective_area(Vector2i(2400,1080),Vector2i(1280,720)),Rect2i(240,0,1920,1080))
	assert_eq(Preferences.effective_area(Vector2i(1920,1080),Vector2i(800,600)),Rect2i(240,0,1440,1080))
	assert_eq(Preferences.effective_area(Vector2i(1280,1024),Vector2i(1280,720)),Rect2i(0,152,1280,720))

func test_lower_3d_resolution_keeps_native_ui_raster_and_effective_bounds():
	var prefs:=Preferences.new("user://display_resolution_unused.cfg")
	var window:=Window.new()
	autofree(window)
	window.size=Vector2i(2400,1080)
	prefs.display_options={"native_resolution":false,"resolution":Vector2i(1280,720)}
	var extent:=prefs.update_display_frame(window)
	assert_eq(extent,Vector2i(1920,1080))
	assert_eq(window.content_scale_mode,Window.CONTENT_SCALE_MODE_CANVAS_ITEMS)
	assert_eq(window.content_scale_aspect,Window.CONTENT_SCALE_ASPECT_KEEP)
	assert_eq(window.content_scale_size,Vector2i(1280,720))
	assert_almost_eq(window.scaling_3d_scale,2.0/3.0,0.001)
	prefs.display_options.native_resolution=true
	extent=prefs.update_display_frame(window)
	assert_eq(extent,window.size)
	assert_almost_eq(window.scaling_3d_scale,1.0,0.001)
