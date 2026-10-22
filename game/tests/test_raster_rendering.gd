extends GutTest

func test_presets_preserve_authored_gi_and_reflections():
	var world := Node3D.new()
	add_child_autofree(world)
	var environment := WorldEnvironment.new()
	environment.environment=ArenaLighting.environment()
	world.add_child(environment)
	var env := environment.environment
	env.sdfgi_enabled=true
	env.ssil_enabled=true
	var prefs := Preferences.new("user://raster_rendering_unused.cfg")
	for index in Preferences.QUALITY_PRESETS.size():
		prefs.values.quality=index
		prefs.values.merge(Preferences.QUALITY_PRESETS[index],true)
		prefs.apply_rendering(world)
		assert_eq(world.get_viewport().msaa_3d,int(prefs.values.antialiasing))
		assert_eq(world.get_viewport().scaling_3d_scale,1.0)
		assert_eq(env.ambient_light_source,Environment.AMBIENT_SOURCE_COLOR)
		assert_true(env.sdfgi_enabled)
		assert_true(env.ssil_enabled)
		assert_eq(env.reflected_light_source,Environment.REFLECTION_SOURCE_SKY)
		assert_almost_eq(float(env.sky.sky_material.get_shader_parameter("reflection_fill_energy")),0.45,0.00001)
