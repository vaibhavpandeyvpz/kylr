extends GutTest

class TraversalStub extends RefCounted:
	var blocked := false
	func crosses_portal(_a,_b): return false
	func supported(_point): return not blocked
	func standing_clear(_point): return not blocked

class CombatStub extends RefCounted:
	var visible := true
	func clear(_a,_b): return visible

class World extends Node3D:
	var elapsed := 0.0
	var gravity := ArenaTuning.GRAVITY
	var phase := "Active"
	var rng := RandomNumberGenerator.new()
	var combat := CombatStub.new()
	var map := {"traversal":TraversalStub.new()}

class Robot extends Node3D:
	var arena_match
	var velocity := Vector3.ZERO
	var yaw := 0.0
	var team := 0
	var robot_id := 0
	var move_input := Vector2.ZERO
	var wants_walk := false
	var wants_sprint := false
	var wants_crouch := false
	func eye(): return global_position+Vector3.UP*1.5
	func can_act(): return true
	func is_on_floor(): return true
	func aim_direction(): return Vector3.FORWARD

class Brain extends RefCounted:
	var robot
	var transition_index := -1
	var airborne_goal := Vector3.INF
	var maneuver_cooldown := 0.0
	var combat_paused := false
	var tuning := {"reaction_delay":0.2,"dodge_cooldown":1.0,"dodge_chance":1.0}

func test_visible_incoming_projectile_requires_reaction_and_safe_ground():
	var world := World.new()
	add_child_autofree(world)
	var robot := Robot.new()
	world.add_child(robot)
	robot.arena_match=world
	var brain := Brain.new()
	brain.robot=robot
	var dodge := ProjectileDodge.new()
	var shot := BallisticProjectile.launch(world,null,"grenade_launcher",Vector3(0,0.9,-8),Vector3.BACK,{"range":100,"projectile_speed":15})
	shot.set_physics_process(false)
	dodge.tick(brain,0.12)
	assert_eq(robot.move_input,Vector2.ZERO,"No instant reaction to a newly seen shot")
	world.elapsed=0.3
	world.map.traversal.blocked=true
	dodge.tick(brain,0.12)
	assert_eq(robot.move_input,Vector2.ZERO,"Never dodge onto unsupported or blocked ground")
	world.map.traversal.blocked=false
	brain.maneuver_cooldown=0
	dodge.tick(brain,0.12)
	assert_gt(absf(robot.move_input.x),0.9,"Sidestep across the incoming trajectory")
	assert_almost_eq(robot.move_input.y,0.0,0.001)
	assert_false(robot.wants_sprint)
	dodge.reset()
	brain.maneuver_cooldown=0
	robot.move_input=Vector2.ZERO
	world.combat.visible=false
	world.elapsed=1
	dodge.tick(brain,0.12)
	world.elapsed=2
	dodge.tick(brain,0.12)
	assert_eq(robot.move_input,Vector2.ZERO,"No awareness of a shot hidden behind cover")

func test_receding_projectile_is_not_an_incoming_threat():
	assert_lt(ProjectileDodge.closest_time(Vector3(0,0,-8),Vector3.FORWARD*15),0.0)
	assert_almost_eq(ProjectileDodge.closest_time(Vector3(0,0,-15),Vector3.BACK*15),1.0,0.001)
