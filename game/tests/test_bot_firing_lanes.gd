extends GutTest

class World extends Node3D:
	var robots: Array=[]
	var combat: ArenaCombat
	var map: ArenaMap
	var match_type := "DM"
	var difficulty := 3
	var phase := "Active"
	var elapsed := 0.0
	var gravity := 19.6
	var rng := RandomNumberGenerator.new()
	var camera: Camera3D
	var local_robot: ArenaRobot

class Actor extends ArenaRobot:
	func _ready():
		set_process(false);set_physics_process(false)
		character={"eye_height":1.55}
	func muzzle() -> Vector3: return eye()+Vector3(0,-.55,-.4)

class Brain extends ArenaBrain:
	func steer(_dt): pass

class StubMap extends ArenaMap:
	func _ready(): pass

func world() -> World:
	var game := World.new();add_child_autofree(game)
	game.combat=ArenaCombat.new(game)
	game.map=StubMap.new();game.map.game=game;game.add_child(game.map);game.map.set_process(false)
	game.map.traversal=TraversalGraph.new(game.map)
	return game

func actor(game: World,point: Vector3) -> Actor:
	var robot := Actor.new();robot.arena_match=game;robot.protection=0;robot.spawn_remaining=0
	game.add_child(robot);robot.position=point;game.robots.append(robot)
	robot.robot_id=game.robots.size()-1
	return robot

func wall(game: World,point: Vector3,size: Vector3) -> StaticBody3D:
	var body := StaticBody3D.new();game.add_child(body);body.position=point
	var shape := CollisionShape3D.new();var box := BoxShape3D.new();box.size=size;shape.shape=box;body.add_child(shape)
	return body

func test_visible_head_does_not_allow_a_pistol_to_fire_from_a_blocked_muzzle():
	var game := world()
	var shooter := actor(game,Vector3.ZERO)
	var victim := actor(game,Vector3(0,0,-8))
	var cover := wall(game,Vector3(0,.7,-4),Vector3(3,1.4,.2))
	await wait_physics_frames(2)
	shooter.brain=Brain.new(shooter);shooter.brain.decision=10000;shooter.brain.target=victim
	shooter.brain.tick(1.0)
	assert_eq(shooter.brain.observed_aim,victim.eye(),"Aim at the exposed head instead of the covered torso")
	assert_false(shooter.wants_fire,"Eye visibility cannot authorize shooting through waist-high cover")
	assert_true(shooter.brain.firing_blocked)
	cover.position.x=10
	await wait_physics_frames(2)
	shooter.brain.tick(1.0)
	assert_true(shooter.wants_fire,"Resume normal firing once the physical muzzle lane clears")
	cover.position=shooter.muzzle()
	await wait_physics_frames(2)
	assert_false(game.combat.firing_lane(shooter,victim.eye(),false),"A muzzle already inside a solid prop is blocked too")
	shooter.brain.validate_fire()
	assert_false(shooter.wants_fire,"Final trigger validation catches cover that moves after the decision")

func test_projectile_width_rejects_a_lane_that_a_pistol_ray_can_use():
	var game := world()
	var shooter := actor(game,Vector3.ZERO)
	var origin := Vector3(0,1,-.4)
	var target := Vector3(0,1,-8)
	wall(game,Vector3(.06,1,-4),Vector3(.04,2,.2))
	await wait_physics_frames(2)
	assert_true(game.combat.firing_lane(shooter,target,false,origin))
	shooter.equipped="pulse_gun"
	assert_false(game.combat.firing_lane(shooter,target,false,origin),"The pulse cylinder clips the prop even though its center ray clears")

func test_walk_route_starts_on_the_reachable_side_of_an_interior_wall():
	var game := world()
	wall(game,Vector3(0,1.5,0),Vector3(.2,3,4))
	await wait_physics_frames(2)
	var traversal := game.map.traversal
	for nav in [traversal.graph,traversal.basic_graph]:
		nav.add_point(0,Vector3(-.4,.015,0))
		nav.add_point(1,Vector3(1.6,.015,0))
		nav.add_point(2,Vector3(2.5,.015,0))
		nav.connect_points(0,2);nav.connect_points(1,2)
	var route := traversal.route(Vector3(.5,.015,0),Vector3(2.5,.015,0),true,true)
	assert_false(route.is_empty())
	if not route.is_empty(): assert_eq(route[0].point,Vector3(1.6,.015,0),"A closer sample across the wall is not an entry route")

func test_grenade_low_arc_clears_a_low_obstacle_and_rejects_a_ceiling():
	var game := world();var shooter := actor(game,Vector3.ZERO);shooter.equipped="grenade_launcher"
	var origin := Vector3(0,1,0);var target := Vector3(0,1,-15)
	var speed: float=Arsenal.WEAPONS.grenade_launcher.projectile_speed
	var direction := BallisticProjectile.launch_direction(origin,target,speed,9)
	var time := 15.0/(-direction.z*speed)
	var endpoint := origin+direction*speed*time-Vector3.UP*9*time*time*.5
	assert_almost_eq(endpoint,target,Vector3.ONE*.001)
	assert_eq(BallisticProjectile.launch_direction(origin,Vector3(0,1,-50),speed,9),Vector3.ZERO,"Reject an unreachable flat-floor shot")
	wall(game,Vector3(0,.7,-7.5),Vector3(3,1.4,.2))
	await wait_physics_frames(2)
	assert_true(game.combat.firing_lane(shooter,target,false,origin),"A valid lob may clear low cover")
	wall(game,Vector3(0,1.65,-7.5),Vector3(3,.2,4))
	await wait_physics_frames(2)
	assert_false(game.combat.firing_lane(shooter,target,false,origin),"The same lob cannot pass through a roof")
