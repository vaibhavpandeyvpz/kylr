extends GutTest

class AimWorld extends Node3D:
	var robots: Array = []
	var camera: Camera3D
	var camera_rig: ArenaCameraRig
	var local_robot

class Shooter extends ArenaRobot:
	func _ready() -> void:
		set_process(false);set_physics_process(false)
	func eye() -> Vector3: return Vector3(1,2,3)

class ImpactTrace extends ArenaCombat:
	var contact: Dictionary
	func projectile_hit(_projectile, _motion: Vector3, _excluded: Array = []) -> Dictionary: return contact
	func clear(_from: Vector3, _to: Vector3) -> bool: return true

func test_real_projectile_contacts_filter_rejected_hits_and_emp_has_no_splash():
	var game := ArenaMatch.new()
	game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_physics_process(false);game.set_process(false)
	game.camera_rig.set_process(false)
	game.phase="Active";game.replicating=true
	var trace := ImpactTrace.new(game)
	game.combat=trace
	var direct: ArenaRobot=game.add_robot(0,"Direct",0,true,"projector")
	var near: ArenaRobot=game.add_robot(1,"Near",1,false,"projector")
	var protected: ArenaRobot=game.add_robot(2,"Protected",1,false,"projector")
	var shooter: ArenaRobot=game.add_robot(3,"Shooter",1,false,"projector")
	game.local_robot=direct
	for robot in [direct,near,protected,shooter]:
		robot.set_physics_process(false);robot.set_process(false);robot.protection=0
	direct.position=Vector3(0,20,0)
	near.position=direct.position+Vector3.UP*2
	protected.position=direct.position+Vector3.RIGHT
	shooter.position=direct.position+Vector3.RIGHT*20
	protected.protection=5
	var point := direct.body_shape.global_position
	trace.contact={"collider":direct,"position":point,"normal":Vector3.UP}
	for weapon in ["grenade_launcher","rocket_launcher","emp_gun"]:
		for robot in [direct,near]: robot.ah=100;robot.sh=100
		game.presentation_events.clear();game.camera_rig.impact_shake.clear()
		if weapon=="grenade_launcher":
			var shot := BallisticProjectile.new()
			shot.game=game;shot.shooter=shooter;shot.weapon=weapon
			shot.profile=Arsenal.WEAPONS[weapon];shot.velocity=Vector3.DOWN*10
			game.add_child(shot);shot.set_physics_process(false)
			shot.impact(trace.contact);shot.queue_free()
		else:
			var shot := ArenaProjectile.new()
			shot.game=game;shot.shooter=shooter;shot.weapon=weapon
			game.add_child(shot);shot.set_physics_process(false)
			shot.global_position=point+Vector3.UP
			shot.direction=Vector3.DOWN
			shot._physics_process(0.05)
		var events := game.presentation_events.filter(func(event):return event.kind=="impact_shake")
		assert_eq(events.size(),1 if weapon=="emp_gun" else 2,weapon+" accepts direct/splash but not protected targets")
		var direct_events := events.filter(func(event):return event.victim==direct.robot_id)
		assert_eq(direct_events.size(),1)
		if direct_events.size()==1:
			assert_almost_eq(float(direct_events[0].strength),0.65 if weapon=="emp_gun" else 1.0,0.00001)
		if weapon!="emp_gun":
			var nearby_events := events.filter(func(event):return event.victim==near.robot_id)
			assert_eq(nearby_events.size(),1)
			if nearby_events.size()==1:
				var radius: float=ArenaTuning.ROCKET_SPLASH_RADIUS if weapon=="rocket_launcher" else Arsenal.WEAPONS.grenade_launcher.splash_radius
				assert_almost_eq(float(nearby_events[0].strength),1.0-2.0/radius,0.00001,"Vertical offset attenuates actual splash feedback")

func test_blast_falloff_uses_full_3d_distance():
	var blast := Vector3(15,3,-8)
	assert_eq(ImpactShake.blast_strength(blast,blast,5),1.0)
	assert_almost_eq(ImpactShake.blast_strength(blast,blast+Vector3.RIGHT*2.5,5),0.5,0.00001)
	assert_almost_eq(ImpactShake.blast_strength(blast,blast+Vector3.UP*2.5,5),0.5,0.00001,"Height counts equally")
	assert_almost_eq(ImpactShake.blast_strength(blast,blast+Vector3(0,3,4),10),0.5,0.00001)
	assert_eq(ImpactShake.blast_strength(blast,blast+Vector3.UP*5,5),0.0)
	assert_eq(ImpactShake.blast_strength(blast,blast+Vector3.UP*6,5),0.0)
	assert_eq(ImpactShake.blast_strength(blast,blast,0),0.0)

func test_shaker_pattern_is_bounded_scales_with_intensity_and_expires():
	var shake := ImpactShake.new()
	assert_eq(shake.sample(0.02),Transform3D.IDENTITY)
	shake.trigger("pistol",50)
	assert_eq(shake.strength,0.0)
	shake.trigger("rocket_launcher",0.1)
	var weak := shake.strength
	shake.clear()
	shake.trigger("rocket_launcher",1)
	assert_gt(shake.strength,weak)
	var changed := false
	for frame in 60:
		if frame<15: shake.trigger("grenade_launcher",1)
		var offset := shake.sample(1.0/60.0)
		changed=changed or offset!=Transform3D.IDENTITY
		assert_lte(offset.origin.length(),0.04001)
		var angles := offset.basis.get_euler().abs()
		assert_lte(maxf(angles.x,maxf(angles.y,angles.z)),0.02001)
		assert_lte(shake.strength,1.0)
	assert_true(changed,"Samples the vendored Shaker pattern")
	assert_eq(shake.sample(1.0),Transform3D.IDENTITY)
	assert_eq(shake.strength,0.0)
	shake.trigger("emp_gun",0.65)
	assert_gt(shake.strength,0.0)
	assert_lt(shake.strength,1.0)

func test_only_accepted_local_impacts_shake_and_replicate_including_self_blasts():
	var game := ArenaMatch.new()
	game.online=true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_physics_process(false)
	game.set_process(false)
	game.camera_rig.set_process(false)
	game.phase="Active"
	game.replicating=true
	var victim: ArenaRobot=game.add_robot(0,"Local",0,true,"projector")
	var shooter: ArenaRobot=game.add_robot(1,"Other",1,false,"projector")
	for robot in [victim,shooter]:
		robot.set_physics_process(false);robot.set_process(false);robot.protection=0
	game.local_robot=victim
	for cause in ["rocket_launcher","grenade_launcher","emp_gun"]:
		game.camera_rig.impact_shake.clear()
		if victim.hit(2.0,shooter,cause): game.impact_at(victim,cause,victim.body_shape.global_position+Vector3.UP*2.5,5)
		assert_gt(game.camera_rig.impact_shake.strength,0.0)
		assert_almost_eq(game.camera_rig.impact_shake.strength,0.65 if cause=="emp_gun" else 0.5,0.00001)
		assert_true(game.presentation_events.any(func(event):return event.kind=="impact_shake" and event.cause==cause and event.victim==0))
	game.camera_rig.impact_shake.clear()
	assert_true(victim.hit(2.0,victim,"rocket_launcher"))
	game.impact_at(victim,"rocket_launcher",victim.body_shape.global_position,5)
	assert_gt(game.camera_rig.impact_shake.strength,0.0,"Self-blast feedback is retained")
	game.camera_rig.impact_shake.clear()
	victim.protection=5
	assert_false(victim.hit(5.0,shooter,"rocket_launcher"))
	assert_eq(game.camera_rig.impact_shake.strength,0.0)
	victim.protection=0
	game.reduced_motion=true
	assert_true(victim.hit(2.0,shooter,"emp_gun"))
	game.impact_at(victim,"emp_gun",victim.body_shape.global_position)
	assert_eq(game.camera_rig.impact_shake.strength,0.0)
	game.reduced_motion=false
	var transport := OnlineTransport.new()
	autofree(transport)
	transport.game=game
	transport.apply_presentation({"kind":"impact_shake","victim":1,"cause":"emp_gun","strength":0.65})
	assert_eq(game.camera_rig.impact_shake.strength,0.0,"Other robots never shake the local view")
	transport.apply_presentation({"kind":"impact_shake","victim":0,"cause":"rocket_launcher","strength":0.3})
	assert_almost_eq(game.camera_rig.impact_shake.strength,0.3,0.00001,"Server strength reaches the local view unchanged")

func test_camera_shake_preserves_aim_and_clears_in_cinematics():
	var rig := ArenaCameraRig.new()
	add_child_autofree(rig)
	rig.set_process(false)
	rig.host.set_process(false)
	rig.host.set_physics_process(false)
	rig.set_gameplay("fpv",Transform3D.IDENTITY,60)
	var base := Transform3D(Basis(Vector3.UP,0.3),Vector3(1,2,3))
	rig.camera.global_transform=base
	rig.impact_shake.trigger("rocket_launcher",1)
	rig._process(0.05)
	assert_ne(rig.camera.global_transform,base,"Rendered camera receives the shake")
	assert_eq(rig.aim_transform(),base,"Authoritative aim retains the unshaken camera pose")
	var world := AimWorld.new()
	add_child_autofree(world)
	world.camera=rig.camera
	world.camera_rig=rig
	var shooter := Shooter.new()
	world.add_child(shooter)
	shooter.human=true
	shooter.arena_match=world
	world.local_robot=shooter
	var combat := ArenaCombat.new(world)
	assert_almost_eq(combat.aim_target(shooter,40),base.origin-base.basis.z*40,Vector3.ONE*0.00001,"Actual weapon sight ignores cosmetic shake")
	rig.camera.global_transform=base
	rig.shake_enabled=false
	rig._process(0.05)
	assert_eq(rig.camera.global_transform,base)
	assert_eq(rig.impact_shake.strength,0.0)
	rig.shake_enabled=true
	rig.impact_shake.trigger("Fall off map",1)
	rig.select("death")
	rig._process(0.05)
	assert_gt(rig.impact_shake.remaining,0.0,"The fall impact shake continues through the death camera")
	rig.impact_shake.trigger("rocket_launcher",1)
	rig.select("opening")
	rig._process(0.05)
	assert_eq(rig.impact_shake.strength,0.0)
