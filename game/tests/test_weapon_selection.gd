extends GutTest

func test_empty_picked_up_weapon_switches_to_pistol_or_reloads_existing_spare():
	var game := ArenaMatch.new()
	game.online = true
	game.authority = false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.phase = "Active"
	var robot: ArenaRobot = game.add_robot(0,"Pilot",0,true,"projector")
	robot.set_physics_process(false)
	robot.set_process(false)
	robot.protection = 0.0
	robot.wants_fire = true
	for weapon in ["rifle","minigun","emp_gun","rocket_launcher","lightning_gun","flamethrower"]:
		robot.reset_inventory()
		robot.equip("pistol")
		robot.pickup_weapon = weapon
		robot.equip(weapon)
		robot.loaded = 0
		robot.packs = 0
		robot.cooldown = 0.2
		game.combat.trigger(robot,0.01)
		assert_eq(robot.equipped,"pistol",weapon+" falls back when empty")
		assert_eq(robot.pickup_weapon,weapon,"The owned slot is retained for a later ammo pickup")
		robot.equip(weapon)
		robot.packs = 1
		game.combat.trigger(robot,0.01)
		assert_eq(robot.equipped,weapon)
		assert_eq(robot.reload_time,2.0,"A collected spare still reloads automatically")
		assert_eq(robot.packs,1,"Spare is consumed only on reload completion")
		robot.reload_time = 0.0

func test_last_rocket_launch_is_not_lost_when_ammo_runs_out():
	var game := ArenaMatch.new()
	game.online = true
	game.authority = false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.phase = "Active"
	var robot: ArenaRobot = game.add_robot(0,"Pilot",0,true,"projector")
	robot.set_physics_process(false)
	robot.set_process(false)
	robot.weapon_vfx.set_physics_process(false)
	robot.protection = 0.0
	robot.pickup_weapon = "rocket_launcher"
	robot.equip("rocket_launcher")
	robot.loaded = 1
	robot.wants_fire = true
	game.combat.trigger(robot,0.01)
	assert_eq(robot.loaded,0)
	game.combat.trigger(robot,0.01)
	assert_eq(robot.equipped,"rocket_launcher","Keep the last launch's rig until its event")
	robot.weapon_vfx._physics_process(0.04)
	var rockets := game.get_children().filter(func(n): return n is ArenaProjectile)
	assert_eq(rockets.size(),1)
	game.combat.trigger(robot,0.01)
	assert_eq(robot.equipped,"pistol")
	assert_eq(rockets[0].weapon,"rocket_launcher")

func test_mouse_wheel_cycles_owned_weapons_only_during_active_control():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	var robot: ArenaRobot = game.add_robot(0, "Pilot", 0, true, "projector")
	game.local_robot = robot
	game.phase = "Active"
	robot.protection = 0
	var app = load("res://scripts/core/app.gd").new()
	autofree(app)
	app.prefs = Preferences.new()
	app.match_node = game
	app.ui = ArenaUI.new()
	autofree(app.ui)
	app.ui.screen = "match"
	var wheel := InputEventMouseButton.new()
	wheel.pressed = true
	wheel.button_index = MOUSE_BUTTON_WHEEL_DOWN
	app._unhandled_input(wheel)
	assert_eq(robot.equipped, "pistol", "An empty pickup slot does not switch")
	robot.pickup_weapon = "rifle"
	app._unhandled_input(wheel)
	assert_eq(robot.equipped, "pistol", "Startup preparation blocks weapon selection")
	app.startup_complete = true
	app.starting_match = true
	app._unhandled_input(wheel)
	assert_eq(robot.equipped, "pistol", "Match preparation blocks weapon selection")
	app.starting_match = false
	app._unhandled_input(wheel)
	assert_eq(robot.equipped, "rifle")
	wheel.button_index = MOUSE_BUTTON_WHEEL_UP
	app._unhandled_input(wheel)
	assert_eq(robot.equipped, "pistol")
	robot.reload_time = 1.0
	app._unhandled_input(wheel)
	assert_eq(robot.equipped, "pistol", "Reload keeps weapon switching locked")
	robot.reload_time = 0
	app.ui.screen = "pause"
	app._unhandled_input(wheel)
	assert_eq(robot.equipped, "pistol", "Menus do not change weapons")
