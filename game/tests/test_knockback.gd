extends GutTest

func test_rocket_splash_falls_off_and_pushes_outward():
	var near := Knockback.rocket(Vector3.RIGHT, 1.0)
	var far := Knockback.rocket(Vector3.LEFT, 9.0)
	assert_gt(near.x, 0.0)
	assert_lt(far.x, 0.0)
	assert_gt(near.length(), far.length())
	assert_gt(far.y, 0.0)
	assert_eq(Knockback.rocket(Vector3.RIGHT, 11.0), Vector3.ZERO)

func test_emp_and_rocket_apply_velocity_without_warping():
	var robot := ArenaRobot.new()
	autofree(robot)
	robot.position=Vector3(3,0,4)
	robot.apply_knockback(Knockback.emp(Vector3.FORWARD))
	assert_eq(robot.position,Vector3(3,0,4))
	assert_eq(robot.knockback_velocity,Vector3.FORWARD*ArenaTuning.EMP_PUSH_SPEED)
	assert_eq(robot.velocity.y,ArenaTuning.EMP_BOUNCE_SPEED)
	robot.apply_knockback(Knockback.rocket(Vector3.FORWARD))
	assert_eq(robot.velocity.y,ArenaTuning.ROCKET_BOUNCE_SPEED)
	assert_lte(robot.knockback_velocity.length(),ArenaTuning.KNOCKBACK_MAX_SPEED)

func test_repeated_impulses_are_bounded_and_vertical_direction_does_not_cancel_bounce():
	var robot := ArenaRobot.new()
	autofree(robot)
	for index in 20: robot.apply_knockback(Knockback.rocket(Vector3.RIGHT))
	assert_almost_eq(robot.knockback_velocity.length(),ArenaTuning.KNOCKBACK_MAX_SPEED,0.001)
	assert_eq(Knockback.emp(Vector3.DOWN).y,ArenaTuning.EMP_BOUNCE_SPEED)

func test_protected_and_friendly_targets_receive_no_impulse():
	var game := ArenaMatch.new()
	autofree(game)
	game.phase="Active"
	game.match_type="TDM"
	var robot := ArenaRobot.new()
	var attacker := ArenaRobot.new()
	autofree(robot)
	autofree(attacker)
	robot.arena_match=game
	attacker.arena_match=game
	attacker.protection=0
	assert_false(robot.hit(10,attacker,"rocket_launcher",Knockback.rocket(Vector3.RIGHT)))
	robot.protection=0
	assert_false(robot.hit(10,attacker,"emp_gun",Knockback.emp(Vector3.RIGHT)))
	assert_eq(robot.knockback_velocity,Vector3.ZERO)
	assert_eq(robot.velocity,Vector3.ZERO)
