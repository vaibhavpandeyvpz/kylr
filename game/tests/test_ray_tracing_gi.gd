extends GutTest

func test_rt_fixtures_disable_reflection_maps_and_restore_each_exit():
	var prefs := Preferences.new("user://reflection_transition_unused.cfg")
	for exit in ["rt", "fixtures"]:
		var env := ArenaLighting.environment(true)
		var sky_material := env.sky.sky_material as ShaderMaterial
		var panorama = sky_material.get_shader_parameter("reflection_panorama")
		prefs.values.quality = 2 # The conjunction also applies to Custom settings.
		prefs.values.fixture_lighting = true
		prefs._apply_environment_reflections(env, true)
		prefs._apply_environment_reflections(env, true)
		assert_eq(env.reflected_light_source, Environment.REFLECTION_SOURCE_DISABLED)
		assert_eq(sky_material.get_shader_parameter("reflection_fill_energy"), 0.0)
		assert_null(sky_material.get_shader_parameter("reflection_panorama"))
		assert_eq(env.background_mode, Environment.BG_COLOR)
		if exit == "fixtures": prefs.values.fixture_lighting = false
		prefs._apply_environment_reflections(env, exit != "rt")
		assert_eq(env.reflected_light_source, Environment.REFLECTION_SOURCE_SKY)
		assert_almost_eq(float(sky_material.get_shader_parameter("reflection_fill_energy")), 0.45, 0.00001)
		assert_eq(sky_material.get_shader_parameter("reflection_panorama"), panorama)
		assert_false(env.has_meta("quality_reflection_maps"))

func test_all_presets_preserve_authored_gi_across_rt_and_fixture_changes():
	var prefs := Preferences.new("user://gi_transition_unused.cfg")
	for quality in 4:
		for enabled in [false, true]:
			var env := Environment.new()
			env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
			env.ambient_light_energy = 0.26
			env.sdfgi_enabled = enabled
			env.ssil_enabled = enabled
			env.set("pathtracing_max_bounces", 3)
			prefs.values.quality = quality
			for fixtures in [false, true]:
				prefs.values.fixture_lighting = fixtures
				prefs._restore_authored_environment_gi(env)
				assert_eq(env.ambient_light_source, Environment.AMBIENT_SOURCE_COLOR)
				assert_almost_eq(env.ambient_light_energy, 0.26, 0.00001)
				assert_eq(env.sdfgi_enabled, enabled)
				assert_eq(env.ssil_enabled, enabled)
				assert_eq(env.get("pathtracing_max_bounces"), 3)
				assert_false(env.has_meta("quality_raster_gi"))

func test_restores_legacy_live_environment_gi_snapshot_once():
	var prefs := Preferences.new("user://gi_legacy_unused.cfg")
	var env := Environment.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_DISABLED
	env.set_meta("quality_raster_gi", {"ambient_light_source":Environment.AMBIENT_SOURCE_COLOR,"sdfgi_enabled":true,"ssil_enabled":true})
	prefs._restore_authored_environment_gi(env)
	assert_eq(env.ambient_light_source, Environment.AMBIENT_SOURCE_COLOR)
	assert_true(env.sdfgi_enabled)
	assert_true(env.ssil_enabled)
	assert_false(env.has_meta("quality_raster_gi"))
	# A later author edit must not be overwritten by a stale snapshot.
	env.ssil_enabled = false
	prefs._restore_authored_environment_gi(env)
	assert_false(env.ssil_enabled)

func test_unavailable_rt_keeps_ultra_raster_gi():
	if Preferences.ray_tracing_unavailable_reason(int(Preferences.DEFAULTS.rt_denoiser)).is_empty():
		pass_test("Requires unsupported/headless rendering")
		return
	var world := Node3D.new()
	add_child_autofree(world)
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.sdfgi_enabled = true
	env.ssil_enabled = true
	environment.environment = env
	world.add_child(environment)
	var prefs := Preferences.new("user://gi_fallback_unused.cfg")
	prefs.values.quality = 3
	prefs.values.fixture_lighting = true
	prefs.values.ray_tracing = true
	prefs.apply_rendering(world)
	assert_eq(env.ambient_light_source, Environment.AMBIENT_SOURCE_COLOR)
	assert_true(env.sdfgi_enabled)
	assert_true(env.ssil_enabled)
	assert_false(env.get("pathtracing_enabled"))
	assert_false(env.has_meta("quality_reflection_maps"))

func test_supported_ultra_applies_gi_policy_to_viewport_environment():
	if not Preferences.ray_tracing_unavailable_reason(int(Preferences.DEFAULTS.rt_denoiser)).is_empty():
		pass_test("Requires graphical RTX rendering")
		return
	var world := Node3D.new()
	add_child_autofree(world)
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment = env
	world.add_child(environment)
	var prefs := Preferences.new("user://gi_supported_unused.cfg")
	prefs.values.quality = 3
	prefs.values.fixture_lighting = true
	prefs.values.ray_tracing = true
	prefs.apply_rendering(world)
	assert_true(env.get("pathtracing_enabled"))
	assert_eq(env.get("pathtracing_max_bounces"), 3)
	assert_eq(env.ambient_light_source, Environment.AMBIENT_SOURCE_COLOR)
	assert_eq(env.reflected_light_source, Environment.REFLECTION_SOURCE_DISABLED)
	prefs.values.fixture_lighting = false
	prefs.apply_rendering(world)
	assert_true(env.get("pathtracing_enabled"))
	assert_eq(env.get("pathtracing_max_bounces"), 3)
	assert_eq(env.ambient_light_source, Environment.AMBIENT_SOURCE_COLOR)
	assert_eq(env.reflected_light_source, Environment.REFLECTION_SOURCE_BG)
