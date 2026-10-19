extends SceneTree

class DuelBrain extends ArenaBrain:
	func steer(_dt): pass

class Target extends ArenaRobot:
	var causes: Array[String] = []
	func hit(amount: float,attacker,cause: String,impulse := Vector3.ZERO) -> bool:
		var accepted := super.hit(amount,attacker,cause,impulse)
		if accepted: causes.append(cause)
		return accepted

func _initialize(): run.call_deferred()

func run():
	for weapon in ["rifle","lightning_gun","rocket_launcher","rocket_blocked","reload"]:
		var game := ArenaMatch.new()
		game.online=true
		game.difficulty=3
		if weapon=="rocket_blocked": game.match_type="TDM"
		root.add_child(game)
		await physics_frame
		game.set_physics_process(false)
		game.phase="Active"
		var floor := StaticBody3D.new()
		game.add_child(floor)
		floor.position=Vector3(100,49.5,0)
		var shape := CollisionShape3D.new()
		shape.shape=BoxShape3D.new()
		shape.shape.size=Vector3(80,1,100)
		floor.add_child(shape)
		var actor: ArenaRobot = game.add_robot(0,"Shooter",0,false,"projector")
		var victim := Target.new()
		victim.arena_match=game
		victim.robot_id=1
		victim.team=1
		victim.head="projector"
		game.add_child(victim)
		game.robots.append(victim)
		for robot in [actor,victim]:
			robot.protection=0
			robot.spawn_remaining=0
			robot.collision_layer=2
			if robot.brain: robot.brain.behavior.queue_free()
			robot.brain=null
		actor.position=Vector3(100,50.01,0)
		var distance := 28 if weapon=="rifle" else 35 if weapon=="lightning_gun" else 15
		victim.position=Vector3(100,50.01,-distance)
		victim.ah=10000
		victim.sh=0
		actor.brain=DuelBrain.new(actor)
		actor.brain.decision=10000
		actor.brain.tuning=actor.brain.tuning.duplicate()
		actor.brain.tuning.headshot_chance=1.0 # Qualify authored-collider aiming, not its probability.
		actor.pickup_weapon="minigun" if weapon=="reload" else "rocket_launcher" if weapon=="rocket_blocked" else weapon
		actor.loaded=4 if weapon=="reload" else 100
		actor.packs=1 if weapon=="reload" else 0
		actor.equip(actor.pickup_weapon)
		if weapon!="reload": actor.brain.target=victim
		if weapon=="rocket_blocked":
			var ally: ArenaRobot=game.add_robot(2,"Ally",0,false,"projector")
			ally.position=Vector3(100,50.01,-2.5)
			ally.protection=0
			ally.spawn_remaining=0
			ally.collision_layer=2
		var secondary_shots := 0
		var shots := 0
		for frame in 360:
			await physics_frame
			if actor.network_shots>shots:
				if actor.wants_secondary: secondary_shots+=actor.network_shots-shots
				shots=actor.network_shots
		var passed := false
		if weapon=="rifle": passed=victim.causes.has("rifle_headshot") and secondary_shots>0
		elif weapon=="lightning_gun": passed=victim.causes.has("lightning_gun") and secondary_shots>0 and shots<=8
		elif weapon=="rocket_launcher": passed=victim.causes.has("rocket_launcher") and actor.equipped==weapon
		elif weapon=="rocket_blocked": passed=actor.equipped=="pistol" and not victim.causes.has("rocket_launcher") and actor.loaded==100
		else: passed=actor.loaded==100 and actor.packs==0 and actor.reload_time==0
		print("EQUIPMENT_PROBE ",weapon," passed=",passed," shots=",shots," secondary=",secondary_shots," damage=",10000-victim.ah," headshots=",victim.causes.count("rifle_headshot")," loaded=",actor.loaded)
		game.free()
		await physics_frame
		if not passed: push_error("Physical equipment probe failed: "+weapon); quit(1); return
	quit()
