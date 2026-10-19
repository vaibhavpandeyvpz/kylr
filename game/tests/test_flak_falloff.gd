extends GutTest

class RayStub extends RefCounted:
	var next_hit := {}
	func projectile_hit(projectile, motion: Vector3, excluded: Array = []) -> Dictionary:
		return ray(projectile.global_position, projectile.global_position+motion, excluded)
	func ray(_from, _to, _excluded) -> Dictionary:
		var result := next_hit
		next_hit = {}
		return result

class AudioStub extends RefCounted:
	func cue(_id, _point): pass

class World extends Node3D:
	var phase := "Active"
	var gravity := ArenaTuning.GRAVITY
	var combat := RayStub.new()
	var audio := AudioStub.new()

func test_bounces_halve_initial_travel_allowance_and_then_curve_down():
	var world := World.new()
	add_child_autofree(world)
	var wall := StaticBody3D.new()
	add_child_autofree(wall)
	var shard := BallisticProjectile.launch(world,null,"flak_cannon",Vector3.ZERO,Vector3.RIGHT,Arsenal.WEAPONS.flak_cannon)
	shard.set_physics_process(false)
	world.combat.next_hit={"position":Vector3(20,0,0),"normal":Vector3.LEFT,"collider":wall}
	shard._physics_process(0.5)
	assert_almost_eq(shard.bounce_falloff,10.0,0.0001)
	shard._physics_process(0.4) # 9 m at half the 45 m/s launch speed.
	assert_eq(shard.velocity.y,0.0)
	shard._physics_process(0.05)
	shard._physics_process(0.1)
	assert_lt(shard.velocity.y,0.0,"The ricochet gains downward velocity after its allowance")
	world.combat.next_hit={"position":shard.position+Vector3.LEFT,"normal":Vector3.RIGHT,"collider":wall}
	shard._physics_process(0.1)
	assert_almost_eq(shard.bounce_falloff,5.0,0.0001)
	assert_eq(shard.bounce_distance,0.0)
	world.combat.next_hit={"position":shard.position+Vector3.RIGHT,"normal":Vector3.LEFT,"collider":wall}
	shard._physics_process(0.1)
	assert_almost_eq(shard.bounce_falloff,2.5,0.0001)
