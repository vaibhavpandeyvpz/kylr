extends GutTest

class SightProbe extends ArenaCombat:
	var origins: Array[Vector3] = []
	func ray(from: Vector3,_to: Vector3,_exclude: Array = [],_mask := 5) -> Dictionary:
		origins.append(from)
		return {}

func test_followed_bot_keeps_its_sight_and_human_keeps_camera_crosshair():
	var game := world()
	var actor := robot(game,0,0)
	actor.bot_aim = Vector3.FORWARD
	var sight := SightProbe.new(game)
	game.combat = sight
	var camera := Camera3D.new()
	add_child_autofree(camera)
	game.camera = camera
	camera.position = Vector3(10,5,10)
	camera.rotation.y = 1.2
	var original := sight.aim_target(actor,20.0)
	game.local_robot = actor
	assert_eq(sight.aim_target(actor,20.0),original,"Following a bot cannot redirect its weapon sight")
	assert_eq(sight.origins.back(),actor.eye())
	var calls := sight.origins.size()
	assert_eq(actor.pose_aim_direction(),actor.aim_direction())
	assert_eq(sight.origins.size(),calls,"Bot pose needs no camera sight query")
	camera.position += Vector3(7,3,2)
	assert_eq(sight.aim_target(actor,20.0),original,"Observer movement cannot alter bot sight")
	actor.human = true
	var expected := camera.global_position-camera.global_basis.z.normalized()*(20.0+camera.global_position.distance_to(actor.eye()))
	assert_eq(sight.aim_target(actor,20.0),expected,"Human crosshair retains the actual camera ray")
	assert_eq(sight.origins.back(),camera.global_position)
	assert_almost_eq(actor.pose_aim_direction(),(sight.aim_target(actor,Arsenal.WEAPONS[actor.equipped].range)-actor.eye()).normalized(),Vector3.ONE*0.000001)

class RobotProbe extends ArenaRobot:
	var damage_received := 0.0
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)
		character = {"eye_height":1.55}
	func muzzle() -> Vector3: return eye()
	func play_event(_clip: String,_duration: float) -> void: pass
	func hit(amount: float,_attacker,_cause: String,_impulse := Vector3.ZERO) -> bool:
		damage_received += amount
		return true

class CombatProbe extends ArenaCombat:
	var occluded := false
	var rolls := 0
	var directions: Array[Vector3] = []
	func clear(_from: Vector3,_to: Vector3) -> bool: return not occluded
	func firing_lane(_robot,_point: Vector3,_secondary: bool,_origin := Vector3.INF,_flight_direction := Vector3.INF) -> bool: return not occluded
	func ray(_from: Vector3,_to: Vector3,_exclude: Array = [],_mask := 5) -> Dictionary: return {}
	func beam_hit(from: Vector3,to: Vector3,radius: float,exclude: Array = []) -> Dictionary:
		var direction := (to-from).normalized()
		var nearest := from.distance_to(to)
		var hit := {}
		for target in game.robots:
			if target.get_rid() in exclude: continue
			var offset: Vector3 = target.eye()-from
			var along := offset.dot(direction)
			if along>0 and along<nearest and (offset-direction*along).length()<radius and not occluded:
				nearest=along
				hit={"collider":target,"position":from+direction*along}
		return hit
	func aim_target(robot,reach: float) -> Vector3: return robot.muzzle()+robot.aim_direction()*reach
	func stop_contact(_robot) -> void: pass
	func update_contact(_robot,_hit: Dictionary) -> void: pass
	func accuracy_error(_robot) -> Vector2:
		rolls += 1
		return Vector2(deg_to_rad(5),0.5*rolls)
	func trace(robot,reach: float,_damage: float,_color: Color,_scoped: bool) -> void:
		directions.append(shot_direction(robot,reach,true))

class PlannerProbe extends ArenaBrain:
	func seek_cover() -> bool: return false
	func commit_goal(destination: Vector3,kind: String) -> bool:
		goal = destination
		goal_kind = kind
		return true

class AimProbe extends PlannerProbe:
	func steer(_dt): pass

class DropProbe extends PlannerProbe:
	func avoid_obstacles(direction: Vector3,_action: String) -> Vector3: return direction

func test_drop_cannot_stop_near_landing_coordinates_while_on_upper_floor():
	var game := world()
	var actor := robot(game,0,0,Vector3(0,7.11,-28.3))
	actor.brain.behavior.queue_free()
	actor.brain = DropProbe.new(actor)
	actor.brain.path = [{"action":"drop","from":Vector3(0,7.25,-29),"point":Vector3(0,0,-28)}]
	actor.brain.goal = Vector3(0,0,-28)
	actor.brain.goal_kind = "repair"
	actor.brain.retarget = 1000
	actor.brain.transition_index = 0
	actor.brain.transition_launched = true
	actor.brain.airborne_goal = Vector3(0,0,-28)
	actor.brain.steer(1.0/60.0)
	assert_gt(actor.move_input.length(),0.0,"Horizontal proximity cannot halt an unfinished vertical drop")

func test_difficulty_fire_windows_have_readable_noob_pauses():
	var fractions := []
	for level in 4:
		var game := world()
		game.difficulty = level
		var actor := robot(game,0,0)
		var fired := 0
		for frame in 720:
			if actor.brain.fire_window(1.0/60.0): fired+=1
		fractions.append(float(fired)/720)
	assert_between(fractions[0],0.4,0.5)
	assert_gt(fractions[1],fractions[0])
	assert_gt(fractions[2],fractions[1])
	assert_eq(fractions[3],1.0)

func test_noob_observes_torso_at_intervals_and_resets_on_lost_sight():
	var game := world()
	game.difficulty = 0
	var actor := robot(game,0,0)
	var victim := robot(game,1,1,Vector3(0,0,-10))
	actor.brain.behavior.queue_free()
	actor.brain = AimProbe.new(actor)
	actor.brain.decision = 10000
	actor.brain.target = victim
	actor.brain.tick(0.01)
	assert_almost_eq(actor.brain.observed_aim.y,victim.eye().y*0.65,0.001)
	var observed: Vector3 = actor.brain.observed_aim
	victim.position.x+=4
	actor.brain.tick(0.01)
	assert_eq(actor.brain.observed_aim,observed,"Noob cannot track fresh movement every frame")
	actor.brain.tick(0.3)
	assert_almost_eq(actor.brain.observed_aim.x,4.0,0.001)
	game.combat.occluded = true
	actor.brain.tick(0.01)
	assert_null(actor.brain.target)
	assert_false(actor.wants_fire)
	assert_eq(actor.brain.fire_time,0.0)

func test_bot_shot_direction_respects_recoil():
	var game := world()
	var actor := robot(game,0,0)
	actor.bot_aim = Vector3.FORWARD
	actor.recoil = 5.0
	assert_almost_eq(rad_to_deg(actor.aim_direction().angle_to(Vector3.FORWARD)),5.0,0.001)
	assert_gt(actor.aim_direction().y,0.0)

func test_beam_tracks_observed_body_without_projectile_lead():
	var game := world()
	game.difficulty = 3
	var actor := robot(game,0,0)
	var victim := robot(game,1,1,Vector3(0,0,-10))
	victim.velocity = Vector3(6,0,0)
	actor.brain.behavior.queue_free()
	actor.brain = AimProbe.new(actor)
	actor.brain.decision = 10000
	actor.brain.target = victim
	actor.pickup_weapon = "lightning_gun"
	actor.equipped = "lightning_gun"
	actor.brain.equipment.last_pickup="lightning_gun"
	actor.brain.equipment.switch_time=100.0
	actor.loaded = 10
	actor.brain.tick(1.0)
	assert_almost_eq(actor.bot_aim.x,0.0,0.001,"Hitscan beams cannot aim ahead of a moving target")
	actor.brain.equipment.switch_time = 100.0 # Isolate aim from the equipment policy.
	actor.brain.equipment.last_pickup = "emp_gun"
	actor.pickup_weapon = "emp_gun"
	actor.equipped = "emp_gun"
	actor.loaded = 10
	victim.position.z = -4.0
	actor.brain.reset_aim()
	actor.brain.tick(1.0)
	assert_almost_eq(actor.bot_aim.x,0.96/sqrt(0.96*0.96+16),.001,"EMP lead uses its actual 25 m/s projectile speed")

func test_rifle_shot_cooldown_blocks_both_inputs_and_survives_target_changes():
	for level in 4:
		var game := world()
		game.difficulty = level
		var actor := robot(game,0,0)
		var victim := robot(game,1,1,Vector3(0,0,-28))
		actor.brain.behavior.queue_free()
		actor.brain = AimProbe.new(actor)
		actor.brain.decision = 10000
		actor.brain.target = victim
		actor.pickup_weapon = "rifle"
		actor.equipped = "rifle"
		actor.brain.equipment.last_pickup="rifle"
		actor.brain.equipment.switch_time=100.0
		actor.loaded = 10
		actor.brain.tick(1.0)
		assert_true(actor.wants_fire)
		assert_true(actor.wants_secondary)
		actor.network_shots += 1
		actor.brain.tick(0.01)
		assert_false(actor.wants_fire,"A completed shot starts deliberate rifle spacing")
		assert_true(actor.wants_secondary,"Scope can stay held while ordinary primary-fire spacing blocks a shot")
		actor.brain.reset_aim()
		actor.brain.tick(0.3)
		assert_gt(actor.brain.precision_cooldown,0.0,"Changing observation cannot reset the shot cooldown")
		assert_false(actor.wants_fire)

func world(mode := "CTF") -> ArenaMatch:
	var game := ArenaMatch.new()
	autofree(game)
	game.phase = "Active"
	game.match_type = mode
	game.map = ArenaMap.new()
	autofree(game.map)
	game.map.game = game
	game.combat = CombatProbe.new(game)
	game.flags = [{"home":Vector3(0,0,25),"point":Vector3(0,0,25),"state":"home","carrier":-1}, {"home":Vector3(0,0,-25),"point":Vector3(0,0,-25),"state":"home","carrier":-1}]
	return game

func robot(game: ArenaMatch,id: int,team: int,point := Vector3.ZERO) -> RobotProbe:
	var actor := RobotProbe.new()
	actor.arena_match = game
	actor.robot_id = id
	actor.team = team
	actor.position = point
	actor.protection = 0
	add_child_autofree(actor)
	game.robots.append(actor)
	actor.brain = PlannerProbe.new(actor)
	return actor

func test_stream_roll_is_held_per_firing_second_and_restart_spends_a_new_roll():
	for weapon in ["lightning_gun","flamethrower"]:
		var game := world()
		var shooter := robot(game,0,0)
		shooter.equipped = weapon
		shooter.loaded = 5
		shooter.wants_fire = true
		var combat := game.combat as CombatProbe
		combat.trigger(shooter,0.01)
		var first := combat.shot_direction(shooter,15,true)
		for tick in 50:
			combat.trigger(shooter,0.01)
			assert_almost_eq(combat.shot_direction(shooter,15,true),first,Vector3.ONE*0.00001)
		assert_eq(combat.rolls,1,weapon+" cannot reroll each damage tick")
		assert_eq(shooter.loaded,3,"Accuracy hold does not change authored ammo cadence")
		combat.trigger(shooter,0.5)
		assert_eq(combat.rolls,2,"Uninterrupted second rolls exactly once")
		assert_eq(shooter.loaded,2)
		assert_false(combat.shot_direction(shooter,15,true).is_equal_approx(first))
		shooter.wants_fire = false
		combat.trigger(shooter,0.01)
		shooter.wants_fire = true
		combat.trigger(shooter,0.01)
		assert_eq(combat.rolls,3,"Restart starts a new funded firing second")
		assert_eq(shooter.loaded,1)
		if weapon == "lightning_gun":
			shooter.wants_fire = false
			shooter.wants_secondary = true
			shooter.cooldown = 1.0
			combat.trigger(shooter,0.01)
			assert_false(shooter.streaming,"Orb mode ends the primary stream even while secondary is held")
			shooter.wants_secondary = false
			shooter.wants_fire = true
			combat.trigger(shooter,0.01)
			assert_eq(combat.rolls,4,"Returning to primary begins a new accuracy hold")

func test_flame_damage_volume_and_visual_endpoint_share_the_cached_error():
	var game := world()
	var shooter := robot(game,0,0)
	shooter.equipped = "flamethrower"
	shooter.streaming = true
	shooter.stream_accuracy_valid = true
	shooter.stream_accuracy_error = Vector2(deg_to_rad(5),0)
	var combat := game.combat as CombatProbe
	var direction := combat.shot_direction(shooter,15,true)
	# This body lies outside the failed-roll beam volume.
	var edge := Vector3.FORWARD.rotated(Vector3.RIGHT,-deg_to_rad(14))*8.0
	var victim := robot(game,1,1,edge)
	combat.flame(shooter)
	assert_eq(victim.damage_received,0.0,"Failed flame accuracy offsets the damage volume")
	victim.position = direction*8.0
	combat.flame(shooter)
	assert_eq(victim.damage_received,1.5,"Direct flame damage is still resolved normally")
	assert_almost_eq(combat.flame_endpoint(shooter,shooter.muzzle()),victim.eye(),Vector3.ONE*0.0001)
	assert_eq(combat.rolls,0,"Contact/presentation queries cannot consume rolls")

func test_occluded_carrier_uses_frozen_memory_then_public_route_not_live_coordinates():
	var game := world()
	var defender := robot(game,1,0)
	var thief := robot(game,8,1,Vector3(0,0,-10))
	game.flags[0].state = "carried"
	game.flags[0].carrier = thief.robot_id
	assert_eq(defender.brain.interception_point(thief.robot_id),thief.position)
	var last: Vector3 = thief.position
	game.combat.occluded = true
	thief.position = Vector3(15,0,-20)
	game.flags[0].point = thief.position
	assert_eq(defender.brain.interception_point(thief.robot_id),last)
	game.elapsed = 3.0
	var search: Vector3 = defender.brain.interception_point(thief.robot_id)
	assert_ne(search,thief.position)
	thief.position += Vector3(7,0,5)
	game.flags[0].point = thief.position
	assert_eq(defender.brain.interception_point(thief.robot_id),search,"Hidden motion cannot move the goal")
	thief.protection = 5
	game.combat.occluded = false
	assert_false(defender.brain.visible_enemy(thief))

func test_roles_reassign_on_flag_roster_and_availability_changes_without_id_modulo():
	var game := world()
	var home := robot(game,1,0,Vector3(0,0,23))
	var attacker := robot(game,4,0,Vector3(0,0,-20))
	var third := robot(game,7,0,Vector3(4,0,0))
	assert_eq(home.brain.team_role(),"defend")
	assert_eq(attacker.brain.team_role(),"attack")
	game.flags[0].state = "dropped"
	game.flags[0].point = attacker.position
	assert_eq(attacker.brain.team_role(),"recover","Distance replaces static ID assignment")
	assert_ne(home.brain.team_role(),"defend","Away flag immediately changes defense")
	attacker.carrying = 1
	game.flags[0].state = "home"
	game.flags[1].state = "carried"
	game.flags[1].carrier = attacker.robot_id
	assert_eq(attacker.brain.team_role(),"extract")
	assert_eq(third.brain.team_role(),"escort")
	third.alive = false
	assert_eq(home.brain.team_role(),"escort","Dead teammate is removed immediately")
	game.robots.erase(attacker)
	game.flags[1].state = "home"
	game.flags[1].carrier = -1
	assert_eq(home.brain.team_role(),"attack","Lone eligible teammate keeps attacking")

func test_human_teammate_cannot_silently_occupy_the_bot_recovery_role():
	var game := world()
	var bot := robot(game,0,0,Vector3(0,0,10))
	var human := robot(game,1,0,Vector3(0,0,24))
	human.human = true
	game.flags[0].state = "dropped"
	game.flags[0].point = human.position
	assert_eq(bot.brain.team_role(),"recover")
	assert_false(game.bot_roles.assignments.has(human.robot_id),"Player input is never assumed to execute an AI assignment")

func fixture(game: ArenaMatch,kind: String,point: Vector3,weapon := "") -> Dictionary:
	var payload := Node3D.new()
	add_child_autofree(payload)
	var entry := {"id":str(game.map.fixtures.size()),"kind":kind,"point":point,"weapon":weapon,"payload":payload,"ready":true,"cooldown":0.0,"occupant":null}
	game.map.fixtures.append(entry)
	return entry

func test_resource_planning_uses_live_collectibility_and_capacity():
	var game := world()
	var actor := robot(game,0,0)
	actor.ep = 70
	var near := fixture(game,"energy",Vector3.RIGHT)
	var far := fixture(game,"energy",Vector3.RIGHT*10)
	near.ready = false
	assert_true(actor.brain.seek_fixture("energy"))
	assert_eq(actor.brain.goal,far.point,"Deploying pickup is skipped")
	far.payload.hide()
	assert_false(actor.brain.seek_fixture("energy"))
	far.payload.show()
	actor.ep = 100
	assert_false(actor.brain.seek_fixture("energy"),"Full resource cannot be pursued")
	actor.pickup_weapon = "rifle"
	actor.loaded = Arsenal.WEAPONS.rifle.capacity
	actor.packs = 3
	fixture(game,"ammo",Vector3.RIGHT,"rifle")
	assert_false(actor.brain.seek_fixture("ammo"),"A full spare pack must fit")
	actor.packs = 2
	assert_true(actor.brain.seek_fixture("ammo"))
	actor.protection = 1
	assert_false(actor.brain.seek_fixture("ammo"))

func test_dm_protects_a_late_lead_and_deprioritizes_feeding_the_visible_leader():
	var game := world("DM")
	game.goal = 25
	var actor := robot(game,0,0)
	var leader := robot(game,1,1,Vector3(0,0,-5))
	actor.kills = 22
	leader.kills = 18
	assert_true(actor.brain.protecting_lead())
	actor.kills = 1
	leader.kills = 20
	leader.equipped = "minigun"
	assert_false(actor.brain.protecting_lead())
	assert_gt(actor.brain.target_cost(leader),actor.position.distance_to(leader.position))
	actor.brain.target = leader
	game.combat.occluded = false
	assert_true(actor.brain.plan_intent("emergency"))
	assert_eq(actor.brain.goal_kind,"avoid_leader")
	actor.equipped = "minigun"
	actor.ah = 100
	assert_false(actor.brain.unfavorable_duel(leader),"Healthy equipped bots still contest the leader")

func test_versioned_difficulty_preserves_locked_table_and_loaded_tuning():
	assert_eq(BotDifficulty.data.schema_version,1.0)
	assert_false(String(BotDifficulty.data.revision).is_empty())
	for index in 4:
		var config := BotDifficulty.profile(index)
		assert_eq(config.accuracy,[0.8,0.9,0.9,1.0][index])
		assert_eq(config.damage,[0.5,0.75,1.0,1.25][index])
		assert_eq(config.reaction_delay,[0.65,0.45,0.30,0.20][index])

func test_real_accuracy_rolls_keep_locked_probabilities_five_degree_misses_and_human_aim():
	var game := world()
	var actor := robot(game,0,0)
	var combat := ArenaCombat.new(game)
	game.rng.seed = 20261001
	for level in 4:
		game.difficulty = level
		var hits := 0
		var bins := [0,0,0,0]
		for shot in 2000:
			var error := combat.accuracy_error(actor)
			if error.x == 0: hits += 1
			else:
				assert_almost_eq(rad_to_deg(error.x),5.0,0.0001)
				bins[mini(3,int(error.y/TAU*4))] += 1
		assert_almost_eq(float(hits)/2000.0,float(BotDifficulty.profile(level).accuracy),0.035)
		if level != 3:
			for bin in bins: assert_gt(bin,20,"Miss azimuth spans the full circle")
	actor.human = true
	var state := game.rng.state
	assert_eq(combat.accuracy_error(actor),Vector2.ZERO)
	assert_eq(game.rng.state,state,"Human aim never consumes bot accuracy RNG")
