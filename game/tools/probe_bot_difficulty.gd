extends SceneTree

class DuelBrain extends ArenaBrain:
	func steer(_dt): pass

func _initialize(): run.call_deferred()

func run():
	var reports := []
	var weapons := ["pistol","minigun"]
	if "--arsenal" in OS.get_cmdline_user_args(): weapons = ["pistol","rifle","minigun","lightning_gun","flamethrower","emp_gun","rocket_launcher"]
	for level in 4:
		for weapon in weapons:
			var game := ArenaMatch.new()
			game.online = true
			game.difficulty = level
			root.add_child(game)
			await physics_frame
			game.set_physics_process(false)
			game.phase = "Active"
			var floor := StaticBody3D.new()
			game.add_child(floor)
			floor.position = Vector3(100,49.5,0)
			var shape := CollisionShape3D.new()
			shape.shape = BoxShape3D.new()
			shape.shape.size = Vector3(60,1,80)
			floor.add_child(shape)
			var shooter := game.add_robot(0,"Shooter",0,false,"projector") as ArenaRobot
			var victim := game.add_robot(1,"Target",1,false,"projector") as ArenaRobot
			for actor in [shooter,victim]:
				var distance := 28 if weapon=="rifle" else 6 if weapon=="flamethrower" else 11
				actor.position = Vector3(100,50.01,0 if actor==shooter else -distance)
				actor.protection = 0
				actor.spawn_remaining = 0
				actor.collision_layer = 2
				if actor.brain: actor.brain.behavior.queue_free()
				actor.brain = null
			victim.ah = 10000
			shooter.brain = DuelBrain.new(shooter)
			shooter.brain.decision = 10000
			shooter.brain.target = victim
			shooter.bot_aim = Vector3.FORWARD
			if weapon!="pistol":
				shooter.pickup_weapon = weapon
				shooter.loaded = 1000
				shooter.equip(weapon)
			game.rng.seed = 1234
			var first_fire := -1.0
			var fired_frames := 0
			var seconds := 12.0
			for frame in int(seconds*60):
				if "--moving" in OS.get_cmdline_user_args():
					var desired_x := 100.0+4.0*sin(float(frame)/60.0*PI/2.0)
					victim.move_input.x = clampf(desired_x-victim.position.x,-1,1)
				await physics_frame
				if shooter.wants_fire:
					fired_frames += 1
					if first_fire<0: first_fire=float(frame)/60
			var report := {"level":level,"weapon":weapon,"damage":10000-victim.ah,"first_fire":first_fire,"trigger_fraction":float(fired_frames)/(seconds*60),"shots":shooter.network_shots,"moving_target":"--moving" in OS.get_cmdline_user_args()}
			reports.append(report)
			print("DIFFICULTY_DUEL ",JSON.stringify(report))
			game.free()
			await physics_frame
	var suffix := OS.get_cmdline_user_args()[0] if not OS.get_cmdline_user_args().is_empty() else "current"
	var file := FileAccess.open("res://reports/bot_difficulty_"+suffix+".json",FileAccess.WRITE)
	file.store_string(JSON.stringify(reports,"  "))
	for index in range(weapons.size(),reports.size()):
		# Small damage variation can arise from knockback and projectile impacts.
		if reports[index].damage<reports[index-weapons.size()].damage*0.95 or reports[index].first_fire>reports[index-weapons.size()].first_fire:
			push_error("Difficulty progression regressed in the seeded duel")
			quit(1)
			return
	quit()
