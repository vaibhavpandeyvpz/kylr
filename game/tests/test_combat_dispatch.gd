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

class CapturedLaunch extends ArenaCombat:
	var locked_id := -99
	func launch(_robot, _weapon: String, _voice: ArenaVoice = null, target_id := -1):
		locked_id = target_id

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
	assert_eq(combat.locked_id, 4, "Changing aim during the muzzle delay cannot redirect a funded shot")
	robot.weapon_vfx.pending.clear()
	robot.cooldown = 0.0
	combat.trigger(robot, 0.01)
	robot.weapon_vfx.pending[0].action.call()
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

func test_both_orb_secondaries_launch_immediately_and_wait_three_quarters_of_a_second():
	for weapon in ["lightning_gun", "flamethrower"]:
		for primary_held in [false, true]:
			var setup := fixture(weapon)
			var robot: ArenaRobot = setup.robot
			robot.wants_fire = primary_held
			robot.wants_secondary = true
			setup.combat.trigger(robot, 0.01)
			assert_false(robot.streaming, "Orb takes precedence when both controls are held")
			assert_eq(robot.loaded, 49)
			assert_eq(robot.cooldown, 0.75)
			assert_eq(robot.recoil, 1.0)
			var orbs := projectiles(setup.world)
			assert_eq(orbs.size(), 1)
			assert_eq(orbs[0].weapon, weapon)
			assert_eq(setup.world.audio.cues, [weapon + "_secondary"])
			robot.cooldown -= 0.5
			setup.combat.trigger(robot, 0.5)
			assert_eq(robot.loaded, 49, "Beam's half-second interval cannot launch another orb")
			assert_eq(projectiles(setup.world).size(), 1)
			robot.cooldown -= 0.25
			setup.combat.trigger(robot, 0.25)
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
