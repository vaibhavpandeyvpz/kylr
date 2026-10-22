extends GutTest

class AudioProbe extends RefCounted:
	var cues: Array[String] = []
	func set_loop(_key, _cue, _point, _active) -> void: pass
	func cue(id, _point, _local, _emitter) -> bool:
		cues.append(id)
		return false

class VfxProbe extends WeaponVfx:
	func begin_shot() -> void: pass
	func shot() -> void: pass

class CombatWorld extends Node3D:
	var robots: Array = []
	var local_robot
	var camera: Camera3D
	var audio := AudioProbe.new()
	var rng := RandomNumberGenerator.new()
	var difficulty := 0

class RobotProbe extends ArenaRobot:
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)
		character = {"eye_height": 1.55}
	func play_event(_clip: String, _duration: float) -> void: pass
	func muzzle() -> Vector3: return eye()

func fixture(weapon: String) -> Dictionary:
	var world := CombatWorld.new()
	add_child_autofree(world)
	var robot := RobotProbe.new()
	world.add_child(robot)
	robot.arena_match = world
	robot.human = true
	robot.protection = 0
	robot.equipped = weapon
	robot.loaded = 50
	robot.weapon_vfx = VfxProbe.new()
	robot.weapon_vfx.robot = robot
	robot.add_child(robot.weapon_vfx)
	world.robots = [robot]
	world.local_robot = robot
	return {"world": world, "robot": robot, "combat": ArenaCombat.new(world)}

class FlameVictim extends RobotProbe:
	var accepted_damage := -1.0
	func hit(amount: float, _attacker, _cause: String, _impulse := Vector3.ZERO, _contact: Dictionary = {}) -> bool:
		accepted_damage = amount
		return amount > 0

class FlameTrace extends ArenaCombat:
	var contact: Dictionary = {}
	var swept_length := 0.0
	var aim_reach := 0.0
	func shot_direction(_robot, reach := -1.0, _continuous := false) -> Vector3:
		aim_reach = reach
		return Vector3.FORWARD
	func beam_hit(origin: Vector3, target: Vector3, _radius: float, _exclude: Array = []) -> Dictionary:
		swept_length = origin.distance_to(target)
		return contact

func test_flame_damage_falls_from_full_at_eight_metres_to_zero_at_ten():
	var setup := fixture("flamethrower")
	var combat := FlameTrace.new(setup.world)
	var robot: ArenaRobot = setup.robot
	robot.streaming = true
	var victim := FlameVictim.new()
	setup.world.add_child(victim)
	for sample in [[1.0,2.0],[8.0,2.0],[9.0,1.0],[10.0,0.0]]:
		combat.contact = {"collider":victim,"position":robot.muzzle()+Vector3.FORWARD*sample[0],"normal":Vector3.BACK}
		combat.flame(robot)
		assert_almost_eq(victim.accepted_damage,sample[1],0.00001)
		assert_almost_eq(combat.swept_length,10.0,0.00001,"Damage sweep stops at the catalog maximum")
	combat.contact = {}
	var endpoint := combat.flame_endpoint(robot,robot.muzzle())
	assert_almost_eq(endpoint.distance_to(robot.muzzle()),10.0,0.00001)
	combat.update_flame_contact(robot)
	assert_almost_eq(combat.swept_length,10.0,0.00001,"Contact audio uses the same range")
	assert_almost_eq(combat.aim_reach,10.0,0.00001)

class CapturedLaunch extends ArenaCombat:
	var locked_id := -99
	var scoped := false
	func launch(_robot, _weapon: String, _voice: ArenaVoice = null, target_id := -1, scoped_shot := false):
		locked_id = target_id
		scoped = scoped_shot

func test_rocket_captures_completed_lock_at_trigger_not_delayed_launch():
	var setup := fixture("rocket_launcher")
	var combat := CapturedLaunch.new(setup.world)
	var robot: ArenaRobot = setup.robot
	robot.wants_secondary = true
	robot.rocket_lock_progress = 1.0
	robot.rocket_lock_target = 4
	combat.trigger(robot, 0.01)
	assert_eq(robot.weapon_vfx.pending.size(), 0, "Secondary scope alone never fires")
	robot.wants_fire = true
	combat.trigger(robot, 0.01)
	assert_eq(robot.loaded, 49)
	assert_eq(robot.weapon_vfx.pending.size(), 1)
	robot.rocket_lock_target = 8
	robot.rocket_lock_progress = 0.0
	robot.wants_secondary = false
	robot.weapon_vfx.pending[0].action.call()
	assert_true(combat.scoped,"Scoped launch speed is captured at trigger time")
	assert_eq(combat.locked_id, 4, "Changing aim during the muzzle delay cannot redirect a funded shot")
	robot.weapon_vfx.pending.clear()
	robot.cooldown = 0.0
	combat.trigger(robot, 0.01)
	robot.weapon_vfx.pending[0].action.call()
	assert_false(combat.scoped)
	assert_eq(combat.locked_id, -1, "Hip fire remains unguided")
	robot.weapon_vfx.pending.clear()

func projectiles(world: Node) -> Array:
	var result: Array = []
	for child in world.get_children():
		if child is ArenaProjectile:
			child.set_process(false)
			child.set_physics_process(false)
			result.append(child)
	return result

func test_both_orb_secondaries_launch_immediately_and_wait_one_quarter_of_a_second():
	for weapon in ["lightning_gun", "flamethrower"]:
		for primary_held in [false, true]:
			var setup := fixture(weapon)
			var robot: ArenaRobot = setup.robot
			robot.wants_fire = primary_held
			robot.wants_secondary = true
			setup.combat.trigger(robot, 0.01)
			assert_false(robot.streaming, "Orb takes precedence when both controls are held")
			assert_eq(robot.loaded, 49)
			assert_eq(robot.cooldown, 0.25)
			assert_eq(robot.recoil, 1.0)
			var orbs := projectiles(setup.world)
			assert_eq(orbs.size(), 1)
			assert_eq(orbs[0].weapon, weapon)
			assert_eq(setup.world.audio.cues, [weapon + "_secondary"])
			robot.cooldown -= 0.1
			setup.combat.trigger(robot, 0.1)
			assert_eq(robot.loaded, 49, "An orb cannot launch before its quarter-second interval")
			assert_eq(projectiles(setup.world).size(), 1)
			robot.cooldown -= 0.15
			setup.combat.trigger(robot, 0.15)
			assert_eq(robot.loaded, 48)
			assert_eq(projectiles(setup.world).size(), 2)

func test_recoil_recovers_in_same_duration_for_every_impulse_size():
	for degrees in [1.0, 2.0, 5.0, 15.0]:
		var robot := ArenaRobot.new()
		autofree(robot)
		robot.apply_recoil(degrees)
		assert_eq(robot.recoil, degrees)
		robot.update_recoil(0.175)
		assert_almost_eq(robot.recoil, degrees * 0.5, 0.00001)
		robot.update_recoil(0.174)
		assert_gt(robot.recoil, 0.0)
		robot.update_recoil(0.001)
		assert_almost_eq(robot.recoil, 0.0, 0.00001)
		robot.update_recoil(1.0)
		assert_eq(robot.recoil, 0.0)

func test_repeated_recoil_adds_remaining_pitch_and_restarts_recovery_with_cap():
	var robot := ArenaRobot.new()
	autofree(robot)
	robot.apply_recoil(2.0)
	robot.update_recoil(0.175)
	robot.apply_recoil(2.0)
	assert_almost_eq(robot.recoil, 3.0, 0.00001)
	robot.update_recoil(0.175)
	assert_almost_eq(robot.recoil, 1.5, 0.00001, "Recovery is timed from the most recent impulse")
	robot.apply_recoil(20.0)
	assert_eq(robot.recoil, ArenaTuning.RECOIL_MAX_DEGREES)
	robot.update_recoil(0.35)
	assert_eq(robot.recoil, 0.0)

func test_discrete_dispatch_applies_full_impulse_and_stream_start_uses_same_cap():
	var setup := fixture("lightning_gun")
	var robot: ArenaRobot = setup.robot
	robot.apply_recoil(14.5)
	robot.wants_fire = true
	setup.combat.trigger(robot, 0.01)
	assert_eq(robot.recoil, ArenaTuning.RECOIL_MAX_DEGREES)
	robot.update_recoil(0.175)
	robot.wants_secondary = true
	setup.combat.trigger(robot, 0.01)
	projectiles(setup.world)
	assert_almost_eq(robot.recoil, 8.5, 0.00001)
	robot.update_recoil(0.35)
	assert_eq(robot.recoil, 0.0)

func test_grenade_launch_has_no_firing_knockback():
	var setup := fixture("grenade_launcher")
	setup.robot.wants_fire=true
	setup.combat.trigger(setup.robot,.01)
	var count := 0
	for child in setup.world.get_children():
		if child is BallisticProjectile:
			child.set_physics_process(false);count+=1
	assert_eq(count,1)
	assert_eq(setup.robot.knockback_velocity,Vector3.ZERO)
	assert_eq(setup.robot.velocity,Vector3.ZERO)

class CapturedTrace extends ArenaCombat:
	var reach := 0.0
	var damage := 0.0
	func trace(_robot, distance: float, amount: float, _color: Color, _scoped: bool) -> void:
		reach=distance
		damage=amount

class CapturedStream extends ArenaCombat:
	var ticks: Array[float] = []
	func trace(_robot, _reach: float, amount: float, _color: Color, _scoped: bool) -> void:
		if amount > 0: ticks.append(amount)
	func flame(_robot) -> void:
		ticks.append(Arsenal.WEAPONS.flamethrower.damage * Arsenal.WEAPONS.flamethrower.damage_tick)
	func update_flame_contact(_robot) -> void: pass

func test_primary_streams_deal_two_damage_every_100_ms_and_twenty_per_second():
	for weapon in ["lightning_gun", "flamethrower"]:
		var setup := fixture(weapon)
		var robot: ArenaRobot = setup.robot
		var combat := CapturedStream.new(setup.world)
		robot.wants_fire = true
		combat.trigger(robot, 0.01)
		assert_eq(combat.ticks, [2.0], weapon + " starts with a full tick")
		for frame in 99:
			if robot.stream_damage_time > 0: robot.stream_damage_time -= 0.01
			combat.trigger(robot, 0.01)
		assert_eq(combat.ticks.size(), 10, weapon + " has ten ticks in [0, 1) seconds")
		var total := 0.0
		for amount in combat.ticks:
			assert_eq(amount, 2.0)
			total += amount
		assert_eq(total, 20.0)
		robot.stream_damage_time = -0.2
		var previous_ticks := combat.ticks.size()
		combat.trigger(robot, 0.01)
		assert_eq(combat.ticks.size() - previous_ticks, 3, "A delayed update catches up discrete ticks")
		for amount in combat.ticks: assert_eq(amount, 2.0, "Catch-up never combines ticks into a larger hit")

func test_restarting_or_switching_streams_cannot_bypass_damage_tick_cooldown():
	var setup := fixture("lightning_gun")
	var robot: ArenaRobot = setup.robot
	var combat := CapturedStream.new(setup.world)
	robot.wants_fire = true
	combat.trigger(robot, 0.01)
	robot.wants_fire = false
	combat.trigger(robot, 0.01)
	robot.stream_damage_time -= 0.05
	robot.wants_fire = true
	combat.trigger(robot, 0.01)
	assert_eq(combat.ticks, [2.0], "Rapid trigger presses cannot grant extra ticks")
	robot.equipped = "flamethrower"
	combat.trigger(robot, 0.01)
	assert_eq(combat.ticks, [2.0], "Switching streams retains the damage cooldown")
	robot.stream_damage_time = 0.0
	combat.trigger(robot, 0.01)
	assert_eq(combat.ticks, [2.0, 2.0])

func test_rifle_uses_separate_scoped_cadence_range_and_damage():
	for scoped in [false,true]:
		var setup:=fixture("rifle")
		var combat:=CapturedTrace.new(setup.world)
		setup.robot.wants_fire=true
		setup.robot.wants_secondary=scoped
		combat.trigger(setup.robot,0.01)
		assert_eq(setup.robot.cooldown,0.5 if scoped else 0.25)
		assert_eq(combat.reach,75.0 if scoped else 50.0)
		assert_eq(combat.damage,25.0 if scoped else 10.0)

func test_projectiles_use_independent_launch_speeds():
	for entry in [["lightning_gun",false,25.0],["flamethrower",false,10.0],["emp_gun",false,25.0],["rocket_launcher",false,15.0],["rocket_launcher",true,20.0]]:
		var setup:=fixture(entry[0])
		setup.combat.launch(setup.robot,entry[0],null,-1,entry[1])
		assert_eq(projectiles(setup.world)[0].speed,entry[2])
