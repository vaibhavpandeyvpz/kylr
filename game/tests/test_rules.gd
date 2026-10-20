extends GutTest

func test_shield_never_spills_damage_into_armor():
	assert_eq(Arsenal.shield_split(50,1),Vector2(10,1))
	assert_eq(Arsenal.shield_split(50,0),Vector2(50,0))
	assert_eq(Arsenal.shield_split(10,100),Vector2(2,8))

func test_emp_falloff_and_rocket_splash_boundaries():
	assert_eq(Arsenal.emp_damage(0),15.0)
	assert_eq(Arsenal.emp_damage(5),15.0)
	assert_eq(Arsenal.emp_damage(10),15.0)
	assert_eq(Arsenal.emp_damage(20),15.0)
	assert_eq(Arsenal.emp_damage(21),12.0)
	assert_eq(Arsenal.emp_damage(22.5),7.5)
	assert_eq(Arsenal.emp_damage(24),3.0)
	assert_eq(Arsenal.emp_damage(25),0.0)
	assert_eq(Arsenal.emp_damage(26),0.0)
	assert_eq(Arsenal.splash_damage(1),10.0)
	assert_eq(Arsenal.splash_damage(10),1.0)
	assert_eq(Arsenal.splash_damage(10.01),0.0)

func test_exact_tie_is_draw_but_earlier_score_wins():
	var entries=[{"name":"A","score":4,"time":20.0},{"name":"B","score":4,"time":20.0}]
	assert_eq(Arsenal.winners(entries,"score","time").size(),2)
	entries[1].time=19.0
	assert_eq(Arsenal.winners(entries,"score","time")[0].name,"B")

func test_all_content_resolves_inside_project():
	for weapon in ContentRegistry.weapons().values():
		assert_true(ResourceLoader.exists("res://assets/models/weapons/%s/%s.glb" % [weapon.model,weapon.model]))
		assert_true(ResourceLoader.exists("res://assets/models/weapons/%s/%s_col.glb" % [weapon.model,weapon.model]))
	for map in MapCatalog.all():
		assert_eq(map.flag_bases.size(),2)
		assert_eq(map.camera_path.size(),2)
		assert_eq(map.camera_focus.size(),1)
		assert_true(FileAccess.file_exists(map.metadata))
	assert_eq(ContentRegistry.characters()[0].heads.size(),5)

