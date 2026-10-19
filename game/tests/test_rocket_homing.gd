extends GutTest

func test_turn_radius_bounds_curvature_and_preserves_speed():
	for dt in [1.0/30.0, 1.0/60.0, 1.0/120.0]:
		for goal in [Vector3.RIGHT, Vector3.BACK, Vector3.UP]:
			var turned := ArenaProjectile.steer_direction(Vector3.FORWARD, goal, 15.0*dt, 5.0)
			assert_almost_eq(turned.length(), 1.0, 0.00001)
			assert_almost_eq(Vector3.FORWARD.angle_to(turned), 15.0*dt/5.0, 0.00001)
	var near := Vector3.FORWARD.rotated(Vector3.UP, 0.001)
	assert_almost_eq(ArenaProjectile.steer_direction(Vector3.FORWARD, near, 0.25, 5.0).distance_to(near), 0.0, 0.00001)

func test_seeker_keeps_original_target_and_drops_it_on_death():
	# Use a lightweight target with the same lifecycle fields to isolate steering.
	var victim := Target.new()
	add_child_autofree(victim)
	victim.position = Vector3(10, 0, -20)
	var rocket := ArenaProjectile.new()
	rocket.weapon = "test"
	add_child_autofree(rocket)
	rocket.set_physics_process(false)
	rocket.set_process(false)
	rocket.homing_target = weakref(victim)
	assert_true(rocket.steer_homing(1.0/60.0))
	assert_gt(rocket.direction.x, 0.0)
	victim.alive = false
	var final_direction := rocket.direction
	assert_false(rocket.steer_homing(1.0/60.0))
	victim.alive = true
	assert_false(rocket.steer_homing(1.0/60.0), "A respawn must not reacquire an old rocket")
	assert_eq(rocket.direction, final_direction)

class Target extends Node3D:
	var alive := true
	var spawn_remaining := 0.0

class LockTrace extends ArenaCombat:
	var seen: ArenaRobot
	func damageable_target(_robot) -> ArenaRobot: return seen

func test_lock_requires_continuous_target_and_releases_with_scope():
	var combat := LockTrace.new(null)
	var shooter := ArenaRobot.new()
	var enemy := ArenaRobot.new()
	var other := ArenaRobot.new()
	autofree(shooter)
	autofree(enemy)
	autofree(other)
	shooter.equipped = "rocket_launcher"
	shooter.wants_secondary = true
	enemy.robot_id = 2
	other.robot_id = 3
	combat.seen = enemy
	combat.update_rocket_lock(shooter, 0.2)
	assert_almost_eq(shooter.rocket_lock_progress, 0.5, 0.00001)
	combat.update_rocket_lock(shooter, 0.2)
	assert_eq(shooter.rocket_lock_progress, 1.0)
	assert_eq(shooter.rocket_lock_target, 2)
	combat.seen = other
	combat.update_rocket_lock(shooter, 0.1)
	assert_almost_eq(shooter.rocket_lock_progress, 0.25, 0.00001)
	combat.seen = null # Shared authoritative trace rejects cover/protected/friendly targets.
	combat.update_rocket_lock(shooter, 0.1)
	assert_eq(shooter.rocket_lock_target, -1)
	assert_eq(shooter.rocket_lock_progress, 0.0)
	combat.seen = enemy
	shooter.wants_secondary = false
	combat.update_rocket_lock(shooter, 1.0)
	assert_eq(shooter.rocket_lock_target, -1)
