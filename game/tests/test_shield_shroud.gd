extends GutTest

func test_all_head_shrouds_share_live_skeleton_and_stay_below_budget():
	var character := ContentRegistry.character("tensor")
	for head in character.heads:
		var body := Assets.model("characters",character.model)
		add_child_autofree(body)
		var skeleton := Assets.find(body,"Skeleton3D") as Skeleton3D
		var robot := {"character":character,"head":head,"tint":Color.CYAN,"skeleton":skeleton}
		var shield := ShieldShroud.install(robot)
		assert_eq(shield.get_parent(),skeleton)
		assert_eq(shield.mesh.get_surface_count(),1,"One material/draw per active shield")
		assert_lte(shield.mesh.surface_get_array_index_len(0)/3,2500)
		assert_false(shield.visible,"Health/protection state controls visibility")
		assert_eq(shield.cast_shadow,GeometryInstance3D.SHADOW_CASTING_SETTING_OFF)
		for bind in shield.skin.get_bind_count():
			assert_eq(shield.skin.get_bind_name(bind),skeleton.get_bone_name(shield.skin.get_bind_bone(bind)))
		assert_eq(shield.find_children("*","CollisionObject3D",true,false).size(),0,"Visual wrapper never adds a hit volume")

func test_shroud_visibility_follows_health_spawn_and_body_visibility():
	var game := ArenaMatch.new()
	game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority=false
	game.phase="Active"
	var robot: ArenaRobot=game.add_robot(0,"Shield probe",0,true,"projector")
	robot.spawn_remaining=0
	robot.protection=0
	robot.sh=100
	robot.show()
	robot._process(0)
	assert_true(robot.shield_mesh.is_visible_in_tree())
	robot.hit_flash = 0.1
	robot._process(0)
	assert_almost_eq(robot.shield_mesh.material_override.get_shader_parameter("hit_progress"),0.5,0.001)
	robot.shield_mesh.material_override.set_shader_parameter("hit_progress",0.125)
	robot._process(0)
	assert_almost_eq(robot.shield_mesh.material_override.get_shader_parameter("hit_progress"),0.5,0.001,"An external edit must not leave stale hit progress")
	var replacement := robot.shield_mesh.material_override.duplicate()
	replacement.set_shader_parameter("hit_progress",0.0)
	robot.shield_mesh.material_override = replacement
	robot._process(0)
	assert_almost_eq(replacement.get_shader_parameter("hit_progress"),0.5,0.001,"A replacement material receives the live hit state")
	robot.hit_flash = 0.0
	robot._process(0)
	assert_almost_eq(replacement.get_shader_parameter("hit_progress"),1.0,0.001)
	robot.body.hide()
	assert_false(robot.shield_mesh.is_visible_in_tree(),"FPV body hiding also hides its shroud")
	robot.body.show()
	robot.sh=0
	robot._process(0)
	assert_false(robot.shield_mesh.visible,"Depleted or expired SH removes the wrapper")
	robot.protection=1
	robot._process(0)
	assert_true(robot.shield_mesh.visible,"Spawn protection uses the same fitted shell")
	robot.spawn_remaining=1
	robot._process(0)
	assert_false(robot.shield_mesh.visible)
	robot.spawn_remaining=0
	robot.alive=false
	robot._process(0)
	assert_false(robot.shield_mesh.visible,"Death removes the wrapper")
