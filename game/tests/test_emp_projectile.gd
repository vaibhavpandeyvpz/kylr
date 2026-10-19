extends GutTest

class Target extends ArenaRobot:
	var damage_taken := 0.0
	func _ready():
		set_process(false)
		set_physics_process(false)
	func hit(amount: float, _attacker, _cause: String, _impulse := Vector3.ZERO) -> bool:
		damage_taken += amount
		return amount > 0

class Contacts extends RefCounted:
	var count := 0
	func emp_contact(_point: Vector3, _normal: Vector3): count += 1
	func fire_contact(_point: Vector3, _normal: Vector3): count += 1
	func electric_contact(_point: Vector3, _normal: Vector3, _broadcast := false): count += 1

class Trace extends RefCounted:
	var target: Target
	var hit_at := INF
	var masks: Array[int] = []
	var endpoint := Vector3.ZERO
	func projectile_hit(projectile, motion: Vector3, excluded: Array = []) -> Dictionary:
		return ray(projectile.global_position, projectile.global_position+motion, excluded)
	func ray(from: Vector3, to: Vector3, _exclude: Array = [], mask := 5) -> Dictionary:
		masks.append(mask)
		endpoint = to
		if target != null and -from.z <= hit_at and -to.z >= hit_at:
			return {"position":Vector3(0,0,-hit_at), "normal":Vector3.BACK, "collider":target}
		return {}
	func play_impact(_weapon, _point, _collider, _shielded, _shooter, _secondary := false): pass

class World extends Node3D:
	var phase := "Active"
	var gravity := 19.6
	var robots: Array = []
	var combat := Trace.new()
	var effects := Contacts.new()

func test_fireball_and_lightning_orb_share_travel_gravity_expiry_and_direct_damage():
	var trajectories: Array = []
	for weapon in ["lightning_gun", "flamethrower"]:
		var world := World.new()
		add_child_autofree(world)
		var shooter := Target.new()
		world.add_child(shooter)
		var shot := ArenaProjectile.new()
		shot.weapon = weapon
		shot.speed = Arsenal.ORB_SPEED
		shot.game = world
		shot.shooter = shooter
		world.add_child(shot)
		shot.set_physics_process(false)
		shot._physics_process(5.0)
		assert_eq(shot.global_position, Vector3(0, 0, -50))
		assert_eq(shot.fall, 0.0)
		shot._physics_process(0.1)
		assert_eq(shot.fall, 0.0, "Gravity begins after 50 m")
		shot._physics_process(0.1)
		assert_gt(shot.fall, 0.0)
		trajectories.append(shot.global_position)
		shot.age = 20.0
		shot._physics_process(0.01)
		assert_true(shot.is_queued_for_deletion())
		var target := Target.new()
		world.add_child(target)
		var nearby := Target.new()
		world.add_child(nearby)
		world.robots = [shooter, target, nearby]
		world.combat.target = target
		world.combat.hit_at = 55.0
		var contact := ArenaProjectile.new()
		contact.weapon = weapon
		contact.speed = Arsenal.ORB_SPEED
		contact.game = world
		contact.shooter = shooter
		world.add_child(contact)
		contact.set_physics_process(false)
		contact.distance = 54.0
		contact.position.z = -54.0
		contact._physics_process(0.2)
		assert_eq(target.damage_taken, 10.0, "No distance falloff beyond 50 m")
		assert_eq(nearby.damage_taken, 0.0, "Orbs have no splash")
		assert_eq(world.effects.count, 1)
		assert_true(contact.is_queued_for_deletion())
	assert_eq(trajectories[0], trajectories[1])

func test_emp_hits_only_first_direct_target_and_uses_exact_contact_distance():
	for hit_at in [5.0, 20.0, 22.5, 24.0]:
		var world := World.new()
		add_child_autofree(world)
		var shooter := Target.new()
		world.add_child(shooter)
		var target := Target.new()
		world.add_child(target)
		var nearby := Target.new()
		world.add_child(nearby)
		nearby.position = Vector3(0.4,0,-5)
		world.robots = [shooter, nearby, target]
		world.combat.target = target
		world.combat.hit_at = hit_at
		var shot := ArenaProjectile.new()
		shot.weapon = "emp_gun"
		shot.speed = 20
		shot.game = world
		shot.shooter = shooter
		world.add_child(shot)
		shot.set_physics_process(false)
		shot._physics_process(2.0)
		assert_almost_eq(target.damage_taken, Arsenal.emp_damage(hit_at), 0.0001)
		assert_eq(nearby.damage_taken, 0.0, "Nearby robots are outside a direct shot")
		assert_almost_eq(shot.distance, hit_at, 0.0001, "Damage uses the contact, not the tick endpoint")
		assert_eq(world.combat.masks, [5], "Ray includes robot hit colliders and walls")
		assert_eq(world.effects.count, 1)
		assert_true(shot.is_queued_for_deletion(), "EMP stops at its first contact")

func test_emp_clamps_last_sweep_and_vanishes_at_twenty_five_metres():
	var world := World.new()
	add_child_autofree(world)
	var shooter := Target.new()
	world.add_child(shooter)
	var beyond := Target.new()
	world.add_child(beyond)
	world.combat.target = beyond
	world.combat.hit_at = 25.01
	var shot := ArenaProjectile.new()
	shot.weapon = "emp_gun"
	shot.speed = 20
	shot.game = world
	shot.shooter = shooter
	world.add_child(shot)
	shot.set_physics_process(false)
	shot._physics_process(2.0)
	assert_eq(world.combat.endpoint, Vector3(0,0,-25))
	assert_eq(shot.distance, 25.0)
	assert_eq(beyond.damage_taken, 0.0)
	assert_eq(world.effects.count, 0, "Range expiry is silent")
	assert_false(shot.visual.visible)
	assert_true(shot.is_queued_for_deletion())
