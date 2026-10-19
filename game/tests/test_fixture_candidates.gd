extends GutTest

class Robot extends CharacterBody3D:
	var robot_id := 0
	var active := true
	var checks := 0
	func can_act() -> bool:
		checks += 1
		return active

class MatchState extends RefCounted:
	var robots: Array = []
	var phase := "Active"

class MapProbe extends ArenaMap:
	var claims: Array = []
	func collect(f: Dictionary,r):
		claims.append(r.robot_id)
		f.cooldown = 1.0

func actor(id: int, point: Vector3) -> Robot:
	var robot := Robot.new()
	robot.robot_id = id
	robot.collision_layer = 2
	var collision := CollisionShape3D.new()
	collision.shape = SphereShape3D.new()
	robot.add_child(collision)
	add_child_autofree(robot)
	robot.position = point
	return robot

func test_overlap_candidates_preserve_roster_priority_and_current_eligibility():
	var map := MapProbe.new()
	autofree(map) # Avoid loading the actual map for this interaction probe.
	map.game = MatchState.new()
	map.config = {"event":{"type":"none"}}
	var trigger := Area3D.new()
	trigger.collision_mask = 2
	var collision := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3.ONE*4
	collision.shape = box
	trigger.add_child(collision)
	add_child_autofree(trigger)
	var second := actor(1,Vector3.RIGHT)
	var first := actor(0,Vector3.LEFT)
	var distant := actor(2,Vector3(100,0,0))
	var outsider := actor(99,Vector3.ZERO) # Overlapping bodies outside the roster cannot collect.
	map.game.robots = [first,second,distant]
	var fixture := {"kind":"ammo","payload":Node3D.new(),"cooldown":0.0,"trigger":trigger,"inside":[]}
	autofree(fixture.payload)
	map.fixtures.append(fixture)
	await wait_physics_frames(3)
	map.tick(0.016)
	assert_eq(map.claims,[0],"Roster order wins, regardless of overlap order")
	assert_eq(fixture.inside,[0,1])
	assert_eq(distant.checks,0,"Distant robots require no eligibility calls")
	fixture.cooldown = 0.0
	first.active = false
	map.tick(0.016)
	assert_eq(map.claims,[0,1],"A changed eligibility state is checked at interaction time")
	assert_eq(fixture.inside,[1])
	first.position = Vector3(100,0,0)
	second.position = Vector3(100,0,0)
	outsider.position = Vector3(100,0,0)
	await wait_physics_frames(3)
	map.tick(0.016)
	assert_eq(fixture.inside,[],"An empty native trigger clears prior occupancy")
	assert_eq(map.claims,[0,1],"Empty triggers grant no pickup")
	fixture.trigger = null
	fixture.point = Vector3.ZERO
	fixture.cooldown = 0.0
	first.active = true
	first.position = Vector3.ZERO
	map.tick(0.016)
	assert_eq(map.claims,[0,1,0],"Fixtures without native triggers retain their proximity fallback")
	assert_eq(fixture.inside,[0])
