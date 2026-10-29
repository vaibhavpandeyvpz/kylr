extends GutTest

class RayStub extends RefCounted:
	var next_hit := {}
	var endpoint := Vector3.ZERO
	func projectile_hit(projectile, motion: Vector3, excluded: Array = []) -> Dictionary:
		endpoint = projectile.global_position+motion
		return ray(projectile.global_position, projectile.global_position+motion, excluded)
	func ray(_from, _to, _excluded) -> Dictionary:
		var result := next_hit
		next_hit = {}
		return result

class AudioStub extends RefCounted:
	func cue(_id, _point): pass

class EffectsStub extends RefCounted:
	func flak_contact(_point, _normal): pass

class Target extends ArenaRobot:
	var damage_taken := 0.0
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)
	func hit(amount: float, _attacker, _cause: String, _impulse := Vector3.ZERO, _contact: Dictionary = {}) -> bool:
		damage_taken += amount
		return amount > 0

class World extends Node3D:
	var phase := "Active"
	var authority := true
	var robots: Array = []
	var gravity := ArenaTuning.GRAVITY
	var combat := RayStub.new()
	var audio := AudioStub.new()
	var effects := EffectsStub.new()

func test_bounces_halve_initial_travel_allowance_and_then_curve_down():
	var world := World.new()
	add_child_autofree(world)
	var wall := StaticBody3D.new()
	add_child_autofree(wall)
	var shard := BallisticProjectile.launch(world,null,"flak_cannon",Vector3.ZERO,Vector3.RIGHT,Arsenal.WEAPONS.flak_cannon)
	shard.set_physics_process(false)
	world.combat.next_hit={"position":Vector3(10,0,0),"normal":Vector3.LEFT,"collider":wall}
	shard._physics_process(10.0/shard.velocity.length()+0.01)
	assert_almost_eq(shard.bounce_falloff,5.0,0.0001)
	shard._physics_process(4.0/shard.velocity.length()) # Stop just short of the 5 m allowance.
	assert_eq(shard.velocity.y,0.0)
	shard._physics_process(1.1/shard.velocity.length())
	shard._physics_process(0.1)
	assert_lt(shard.velocity.y,0.0,"The ricochet gains downward velocity after its allowance")
	world.combat.next_hit={"position":shard.position+Vector3.LEFT,"normal":Vector3.RIGHT,"collider":wall}
	shard._physics_process(0.1)
	assert_almost_eq(shard.bounce_falloff,2.5,0.0001)
	assert_eq(shard.bounce_distance,0.0)
	world.combat.next_hit={"position":shard.position+Vector3.RIGHT,"normal":Vector3.LEFT,"collider":wall}
	shard._physics_process(0.1)
	assert_almost_eq(shard.bounce_falloff,1.25,0.0001)

func test_flak_damage_uses_swept_contact_distance_before_the_tick_endpoint():
	for sample in [[5.0,5.0],[25.0,5.0],[26.0,4.0],[27.5,2.5],[29.0,1.0],[30.0,0.0]]:
		var world := World.new()
		add_child_autofree(world)
		var target := Target.new()
		world.add_child(target)
		var shard := BallisticProjectile.launch(world,null,"flak_cannon",Vector3.ZERO,Vector3.RIGHT,Arsenal.WEAPONS.flak_cannon)
		shard.set_physics_process(false)
		world.combat.next_hit={"position":Vector3(sample[0],0,0),"normal":Vector3.LEFT,"collider":target}
		shard._physics_process(2.0)
		assert_almost_eq(shard.travelled,sample[0],0.00001)
		assert_almost_eq(target.damage_taken,sample[1],0.00001)
		assert_true(shard.is_queued_for_deletion())

func test_flak_final_sweep_is_clamped_to_thirty_metres_and_expires_immediately():
	var world := World.new()
	add_child_autofree(world)
	var shard := BallisticProjectile.launch(world,null,"flak_cannon",Vector3.ZERO,Vector3.RIGHT,Arsenal.WEAPONS.flak_cannon)
	shard.set_physics_process(false)
	shard._physics_process(29.0/30.0)
	assert_false(shard.is_queued_for_deletion())
	shard._physics_process(1.0)
	assert_eq(world.combat.endpoint,Vector3(30,0,0))
	assert_eq(shard.travelled,30.0)
	assert_eq(shard.global_position,Vector3(30,0,0))
	assert_true(shard.is_queued_for_deletion())

func test_ricochet_damage_counts_total_travel_instead_of_distance_from_the_muzzle():
	var world := World.new()
	add_child_autofree(world)
	var wall := StaticBody3D.new()
	world.add_child(wall)
	var target := Target.new()
	world.add_child(target)
	var shard := BallisticProjectile.launch(world,null,"flak_cannon",Vector3.ZERO,Vector3.RIGHT,Arsenal.WEAPONS.flak_cannon)
	shard.set_physics_process(false)
	world.combat.next_hit={"position":Vector3(20,0,0),"normal":Vector3.LEFT,"collider":wall}
	shard._physics_process(0.7)
	world.combat.next_hit={"position":shard.global_position+Vector3.LEFT*7.5,"normal":Vector3.RIGHT,"collider":target}
	shard._physics_process(1.0)
	assert_almost_eq(shard.travelled,27.5,0.00001)
	assert_almost_eq(target.damage_taken,2.5,0.00001,"Ricochets never reset damage falloff")
