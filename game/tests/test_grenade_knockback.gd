extends GutTest
class Audio extends RefCounted:
	func cue(_id,_point): pass
class Effects extends RefCounted:
	func grenade_explosion(_point,_normal): pass
class Combat extends ArenaCombat:
	var covered := false
	func clear(_from: Vector3,_to: Vector3) -> bool: return not covered
class World extends Node3D:
	var authority := true
	var phase := "Active"
	var match_type := "DM"
	var robots: Array=[]
	var audio := Audio.new()
	var effects := Effects.new()
	var combat: Combat
class Actor extends ArenaRobot:
	var damage := 0.0
	var hits := 0
	func _ready():
		set_process(false);set_physics_process(false);character={"eye_height":1.55}
	func hit(amount: float,attacker,_cause: String,impulse := Vector3.ZERO) -> bool:
		if amount<=0 or not can_take_damage(attacker): return false
		damage+=amount;hits+=1;apply_knockback(impulse);return true
func actor(game: World,x: float) -> Actor:
	var robot := Actor.new();robot.arena_match=game;robot.protection=0;game.add_child(robot)
	robot.position.x=x;game.robots.append(robot);return robot
func setup_case() -> BallisticProjectile:
	var game := World.new();add_child_autofree(game);game.combat=Combat.new(game)
	var projectile := BallisticProjectile.new();projectile.game=game;projectile.weapon="grenade_launcher"
	projectile.profile=Arsenal.WEAPONS.grenade_launcher;projectile.velocity=Vector3.RIGHT*15
	game.add_child(projectile);projectile.set_physics_process(false)
	projectile.shooter=actor(game,-4)
	return projectile
func test_direct_hit_pushes_once_and_splash_pushes_outward_with_falloff():
	var grenade := setup_case();var game: World=grenade.game
	var direct := actor(game,0);var near := actor(game,2);var far := actor(game,4.5)
	grenade.impact({"collider":direct,"position":direct.eye(),"normal":Vector3.LEFT})
	assert_eq(direct.damage,40.0);assert_eq(direct.hits,1,"No double direct and splash damage")
	assert_eq(direct.knockback_velocity.x,ArenaTuning.GRENADE_PUSH_SPEED)
	assert_eq(direct.velocity.y,ArenaTuning.GRENADE_BOUNCE_SPEED)
	assert_almost_eq(near.damage,9.0,.001)
	assert_gt(near.knockback_velocity.x,far.knockback_velocity.x)
	assert_gt(far.velocity.y,0.0)
	assert_lt(game.robots[0].knockback_velocity.x,0.0,"Self-splash pushes away from the explosion")
func test_cover_blocks_splash_damage_and_bounce_together():
	var grenade := setup_case();var game: World=grenade.game
	var victim := actor(game,2);game.combat.covered=true
	grenade.impact({"collider":null,"position":Vector3(0,1.55,0),"normal":Vector3.UP})
	assert_eq(victim.damage,0.0);assert_eq(victim.knockback_velocity,Vector3.ZERO);assert_eq(victim.velocity.y,0.0)
func test_rejected_protected_and_friendly_hits_receive_no_grenade_push():
	var grenade := setup_case();var game: World=grenade.game;game.match_type="TDM"
	var protected := actor(game,0);protected.team=1;protected.protection=5
	var ally := actor(game,2)
	grenade.impact({"collider":protected,"position":protected.eye(),"normal":Vector3.LEFT})
	for victim in [protected,ally]:
		assert_eq(victim.damage,0.0);assert_eq(victim.knockback_velocity,Vector3.ZERO);assert_eq(victim.velocity.y,0.0)
