extends GutTest

class Target extends Node3D:
	var team:=0
	var alive:=true
	var spawn_remaining:=0.0

class World extends RefCounted:
	var robots: Array=[]
	var authority:=true
	var phase:="Active"
	var match_type:="DM"

func test_pulse_gun_selects_closest_opponent_with_inclusive_twenty_metre_range():
	var world:=World.new()
	var controller:=PulseGunController.new()
	autofree(controller)
	controller.game=world
	controller.asset=Node3D.new()
	add_child_autofree(controller.asset)
	controller.settings={"range":20.0,"enabled_match_types":["TDM","CTF"]}
	for entry in [[0,1.0],[1,20.0],[1,20.01],[1,10.0]]:
		var target:=Target.new()
		add_child_autofree(target)
		target.team=entry[0];target.position.x=entry[1]
		world.robots.append(target)
	assert_same(controller.nearest_enemy(),world.robots[3])
	world.robots[3].alive=false
	assert_same(controller.nearest_enemy(),world.robots[1])
	world.robots[1].spawn_remaining=1.0
	assert_null(controller.nearest_enemy())
	controller.cooldown=1.0
	controller._physics_process(0.5)
	assert_eq(controller.cooldown,1.0,"DM disables the gun before aiming/firing or cooldown work")
