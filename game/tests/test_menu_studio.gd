extends GutTest

class MenuHost extends Node:
	var match_node = null

func test_match_presets_do_not_relight_or_downscale_menu_studios():
	var host := MenuHost.new()
	host.set_meta("menu_studio_host",true)
	add_child_autofree(host)
	var studio := MenuStudio.create(get_tree(),Vector2i(320,400))
	autofree(studio)
	var world: WorldEnvironment = studio.find_children("*","WorldEnvironment",true,false)[0]
	var environment := world.environment
	var key: AreaLight3D = studio.get_node("LGT_Preview_Key")
	var prefs := Preferences.new("user://menu_studio_test.cfg")
	var viewport := get_viewport()
	var before := [viewport.msaa_3d,viewport.scaling_3d_mode,viewport.scaling_3d_scale]
	for preset in Preferences.QUALITY_PRESETS:
		for setting in preset: prefs.values[setting] = preset[setting]
		prefs.apply_rendering(host)
		assert_eq(studio.scaling_3d_scale,1.0)
		assert_eq(studio.msaa_3d,Viewport.MSAA_4X)
		assert_almost_eq(environment.ambient_light_energy,0.26,0.001)
		assert_true(environment.ssao_enabled)
		assert_true(environment.glow_enabled)
		assert_almost_eq(key.light_energy,4.0,0.001)
		assert_true(key.shadow_enabled)
	viewport.msaa_3d=before[0]
	viewport.scaling_3d_mode=before[1]
	viewport.scaling_3d_scale=before[2]

func test_separate_menu_views_keep_independent_worlds_and_environment_state():
	var first := MenuStudio.create(get_tree(),Vector2i(320,400))
	var second := MenuStudio.create(get_tree(),Vector2i(320,400))
	autofree(first)
	autofree(second)
	assert_ne(first.world_3d,second.world_3d)
	assert_ne(first.world_3d,get_viewport().world_3d)
	var a: WorldEnvironment = first.find_children("*","WorldEnvironment",true,false)[0]
	var b: WorldEnvironment = second.find_children("*","WorldEnvironment",true,false)[0]
	a.environment.ambient_light_energy=0.0
	assert_almost_eq(b.environment.ambient_light_energy,0.26,0.001)
