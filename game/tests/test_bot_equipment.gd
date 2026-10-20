extends GutTest

var production_weapons: Dictionary
func before_each():
	# Policy fixtures require a strict upgrade order independent of live balance ties.
	production_weapons=Arsenal.WEAPONS
	Arsenal.WEAPONS=production_weapons.duplicate(true)
	Arsenal.WEAPONS.pistol.damage=1.0
	Arsenal.WEAPONS.emp_gun.damage=1.0

func after_each():
	Arsenal.WEAPONS=production_weapons


class Actor extends ArenaRobot:
	func _ready():
		set_process(false)
		set_physics_process(false)
		character={"eye_height":1.55}
	func equip(id: String): equipped=id
	func start_reload(): reload_time=2.0
	func muzzle() -> Vector3: return eye()

class Combat extends ArenaCombat:
	var blocked := false
	func clear(_from: Vector3,_to: Vector3) -> bool: return not blocked
	func ray(_from: Vector3,to: Vector3,_exclude: Array=[],_mask := 5) -> Dictionary: return {"position":to} if blocked else {}
	func firing_lane(_robot,_point: Vector3,_secondary: bool,_origin := Vector3.INF,_flight_direction := Vector3.INF) -> bool: return not blocked

class Brain extends ArenaBrain:
	var reject := Vector3.INF
	func steer(_dt): pass
	func equipment_travel(point: Vector3) -> float: return resource_cost(point)
	func commit_goal(point: Vector3,kind: String) -> bool:
		if point==reject: return false
		goal=point
		goal_kind=kind
		return true

func setup_case(level := 1,mode := "DM") -> Actor:
	var game := ArenaMatch.new()
	autofree(game)
	game.phase="Active"
	game.difficulty=level
	game.match_type=mode
	game.map=ArenaMap.new()
	autofree(game.map)
	game.map.game=game
	game.combat=Combat.new(game)
	var actor := Actor.new()
	actor.arena_match=game
	actor.protection=0
	actor.spawn_remaining=0
	add_child_autofree(actor)
	game.robots.append(actor)
	actor.brain=Brain.new(actor)
	actor.brain.decision=10000
	return actor

func opponent(actor: Actor,distance: float) -> Actor:
	var victim := Actor.new()
	victim.arena_match=actor.arena_match
	victim.team=1
	victim.robot_id=1
	victim.protection=0
	victim.spawn_remaining=0
	add_child_autofree(victim)
	victim.position=Vector3(0,0,-distance)
	actor.arena_match.robots.append(victim)
	actor.brain.target=victim
	actor.brain.observed_aim=victim.eye()
	return victim

func fixture(actor: Actor,kind: String,weapon: String,point: Vector3) -> Dictionary:
	var payload := Node3D.new()
	add_child_autofree(payload)
	var entry := {"id":str(actor.arena_match.map.fixtures.size()),"kind":kind,"weapon":weapon,"point":point,"payload":payload,"ready":true,"cooldown":0.0}
	actor.arena_match.map.fixtures.append(entry)
	return entry

func test_production_balance_accepts_a_first_minigun_even_when_pistol_damage_ties():
	Arsenal.WEAPONS=production_weapons.duplicate(true)
	var actor:=setup_case()
	var available:=fixture(actor,"weapon","minigun",Vector3.RIGHT*2)
	assert_true(actor.brain.equipment.plan(true))
	assert_eq(actor.brain.goal,available.point)
	actor.pickup_weapon="minigun"
	actor.equipped="minigun"
	actor.loaded=100
	actor.brain.equipment.tick(0.1)
	assert_eq(actor.equipped,"minigun","A freshly collected equal-DPS weapon is retained")

func test_visible_threat_changes_pickup_score_without_rejecting_a_short_detour():
	Arsenal.WEAPONS=production_weapons.duplicate(true)
	var actor:=setup_case(3)
	opponent(actor,4)
	var available:=fixture(actor,"weapon","minigun",Vector3.RIGHT*2)
	assert_gt(actor.brain.resource_cost(available.point),6.0,"Exposure alone exceeds the old combat detour ceiling")
	assert_true(actor.brain.equipment.plan(true))
	assert_eq(actor.brain.goal,available.point)

func test_production_flak_scores_the_whole_close_range_pellet_volley():
	Arsenal.WEAPONS=production_weapons.duplicate(true)
	var actor:=setup_case()
	assert_gt(actor.brain.equipment.utility("flak_cannon",2),actor.brain.equipment.utility("pistol",2))
	assert_lt(actor.brain.equipment.utility("flak_cannon",35),actor.brain.equipment.utility("flak_cannon",2))

func test_switches_to_pistol_for_range_and_back_when_pickup_is_suitable():
	var actor := setup_case()
	var victim := opponent(actor,55)
	actor.pickup_weapon="flamethrower"
	actor.loaded=40
	actor.equipped="flamethrower"
	actor.brain.equipment.tick(0.1)
	assert_eq(actor.equipped,"pistol")
	assert_eq(actor.loaded,40,"Changing guns cannot grant or consume ammunition")
	victim.position.z=-6
	actor.brain.observed_aim=victim.eye()
	actor.brain.equipment.tick(1.3)
	assert_eq(actor.equipped,"flamethrower")

func test_rocket_avoids_close_self_blast_and_nearby_geometry():
	var actor := setup_case()
	var victim := opponent(actor,3)
	assert_eq(actor.brain.equipment.utility("rocket_launcher",3),0.0)
	victim.position.z=-15
	assert_gt(actor.brain.equipment.utility("rocket_launcher",15),actor.brain.equipment.utility("pistol",15))
	actor.arena_match.combat.blocked=true
	assert_eq(actor.brain.equipment.utility("rocket_launcher",15),0.0)

func test_urgent_ammo_uses_total_stock_matching_readiness_and_reachability():
	for level in 4:
		var actor := setup_case(level)
		actor.pickup_weapon="minigun"
		actor.loaded=4
		fixture(actor,"ammo","rifle",Vector3.RIGHT)
		var first := fixture(actor,"ammo","minigun",Vector3.RIGHT*2)
		first.ready=false
		var blocked := fixture(actor,"ammo","minigun",Vector3.RIGHT*3)
		actor.brain.reject=blocked.point
		var available := fixture(actor,"ammo","minigun",Vector3.RIGHT*4)
		assert_true(actor.brain.plan_intent("equipment_urgent"))
		assert_eq(actor.brain.goal,available.point)
		assert_eq(actor.brain.goal_kind,"ammo")
		actor.packs=2
		assert_false(actor.brain.equipment.plan(true),"A low magazine with ample reserves is not a supply emergency")

func test_safe_reload_waits_for_a_quiet_opening_and_requires_a_spare():
	for level in 4:
		var actor := setup_case(level)
		actor.pickup_weapon="minigun"
		actor.loaded=10
		actor.packs=1
		opponent(actor,10)
		actor.brain.equipment.tick(0.1)
		assert_eq(actor.reload_time,0.0,"Do not discard a usable magazine in a visible duel")
		actor.brain.target=null
		actor.brain.memory=2.4
		actor.brain.equipment.tick(0.1)
		assert_eq(actor.reload_time,0.0,"Recently lost sight is not a safe reload opening")
		actor.brain.memory=0
		actor.brain.equipment.tick(0.1)
		assert_eq(actor.reload_time,2.0)
		actor.reload_time=0
		actor.packs=0
		actor.brain.equipment.tick(0.1)
		assert_eq(actor.reload_time,0.0)

func test_weapon_upgrade_is_worth_the_trip_and_rejects_a_nearby_downgrade():
	var actor := setup_case()
	actor.pickup_weapon="minigun"
	actor.loaded=100
	fixture(actor,"weapon","emp_gun",Vector3.RIGHT)
	fixture(actor,"weapon","rifle",Vector3.RIGHT*2)
	assert_false(actor.brain.equipment.plan(false))
	actor.pickup_weapon="rifle"
	var rocket := fixture(actor,"weapon","rocket_launcher",Vector3.RIGHT*8)
	assert_true(actor.brain.equipment.plan(false))
	assert_eq(actor.brain.goal,rocket.point)
	rocket.ready=false
	assert_false(actor.brain.equipment.plan(false))

func test_carrier_only_takes_a_nearby_critical_refill():
	var actor := setup_case(3,"CTF")
	actor.carrying=1
	actor.pickup_weapon="minigun"
	actor.loaded=2
	fixture(actor,"weapon","rocket_launcher",Vector3.RIGHT)
	fixture(actor,"ammo","minigun",Vector3.RIGHT*8)
	assert_false(actor.brain.equipment.plan(true))
	var nearby := fixture(actor,"ammo","minigun",Vector3.RIGHT*3)
	assert_true(actor.brain.equipment.plan(true))
	assert_eq(actor.brain.goal,nearby.point)
	actor.packs=2
	assert_false(actor.brain.equipment.plan(false))

func test_dm_lead_protection_does_not_treat_reserves_as_an_ammo_emergency():
	var actor := setup_case()
	actor.arena_match.goal=25
	actor.kills=22
	actor.pickup_weapon="minigun"
	actor.loaded=0
	actor.packs=2
	fixture(actor,"ammo","minigun",Vector3.RIGHT)
	assert_true(actor.brain.protecting_lead())
	assert_false(actor.brain.plan_intent("emergency"))

func test_scoped_rifle_can_fire_past_primary_range_and_orbs_use_projectile_lead():
	var actor := setup_case(3)
	var victim := opponent(actor,70)
	actor.pickup_weapon="rifle"
	actor.equipped="rifle"
	actor.loaded=30
	actor.brain.tick(1.0)
	assert_true(actor.wants_fire)
	assert_true(actor.wants_secondary)
	actor.ammo_entry("rifle").loaded=0
	actor.pickup_weapon="lightning_gun"
	actor.equipped="lightning_gun"
	actor.loaded=30
	victim.position.z=-35
	victim.velocity=Vector3(4,0,0)
	actor.brain.reset_aim()
	actor.brain.observed_aim=victim.eye()
	actor.brain.tick(1.0)
	assert_true(actor.wants_secondary)
	assert_gt(actor.bot_aim.x,0.05)
	assert_eq(actor.brain.equipment.reach("lightning_gun",35),40.0)

func test_fireball_and_lightning_orb_are_used_beyond_stream_range():
	for weapon in ["flamethrower","lightning_gun"]:
		var actor := setup_case(3)
		opponent(actor,35)
		actor.pickup_weapon=weapon
		actor.equipped=weapon
		actor.loaded=30
		actor.brain.tick(1.0)
		assert_true(actor.wants_fire,weapon)
		assert_true(actor.wants_secondary,weapon)
		assert_gt(actor.brain.equipment.utility(weapon,35),0.0)

func test_rocket_scope_stays_held_while_waiting_for_a_completed_lock():
	var actor := setup_case(3)
	var victim := opponent(actor,25)
	actor.pickup_weapon="rocket_launcher"
	actor.equipped="rocket_launcher"
	actor.loaded=20
	actor.brain.tick(1.0)
	assert_true(actor.wants_secondary)
	assert_false(actor.wants_fire,"Acquire the ordinary lock before launching")
	actor.rocket_lock_target=victim.robot_id
	actor.rocket_lock_progress=1.0
	actor.brain.tick(0.1)
	assert_true(actor.wants_secondary)
	assert_true(actor.wants_fire)

func test_headshot_aim_uses_exposed_authored_collider_not_eye_height():
	var actor := setup_case(3)
	var victim := opponent(actor,28)
	var head := StaticBody3D.new()
	victim.add_child(head)
	head.set_meta("hit_region","head")
	var shape := CollisionShape3D.new()
	head.add_child(shape)
	shape.shape=SphereShape3D.new()
	shape.position=Vector3(0.15,1.7,0)
	actor.brain.tuning=actor.brain.tuning.duplicate()
	actor.brain.tuning.headshot_chance=1.0
	actor.pickup_weapon="rifle"
	actor.equipped="rifle"
	actor.loaded=20
	actor.brain.tick(1.0)
	assert_eq(actor.brain.observed_aim,shape.global_position)
	victim.velocity=Vector3(20,0,0)
	actor.network_shots+=1
	actor.brain.tick(0.1)
	assert_false(actor.brain.aiming_head,"Fast motion makes the larger body target preferable")
	assert_almost_eq(actor.brain.observed_aim.y,victim.eye().y*0.65,0.001)

func test_policy_compares_every_owned_gun_and_preserves_other_stock():
	var actor := setup_case()
	var victim := opponent(actor,10)
	actor.pickup_weapon="rifle"
	actor.loaded=30
	actor.pickup_weapon="minigun"
	actor.loaded=100
	actor.brain.equipment.tick(.1)
	assert_eq(actor.equipped,"minigun")
	assert_eq(actor.ammo_for("rifle").loaded,30)
	actor.ammo_entry("minigun").loaded=0
	victim.position.z=-40
	actor.brain.observed_aim=victim.eye()
	actor.brain.equipment.tick(1.3)
	assert_eq(actor.equipped,"rifle")
	assert_eq(actor.loaded,30)

func test_empty_equipped_gun_keeps_its_rig_until_shared_automatic_reload():
	var actor := setup_case()
	actor.pickup_weapon="minigun"
	actor.equipped="minigun"
	actor.loaded=0
	actor.packs=1
	actor.brain.equipment.tick(.1)
	assert_eq(actor.equipped,"minigun")
	actor.handle_empty_weapon()
	assert_eq(actor.reload_time,2.0)
	assert_eq(actor.packs,1)

func test_pistol_can_recover_an_owned_empty_gun_with_banked_spares():
	var actor := setup_case()
	actor.pickup_weapon="minigun"
	actor.loaded=0
	actor.packs=1
	actor.brain.equipment.tick(.1)
	assert_eq(actor.equipped,"minigun")
	assert_eq(actor.reload_time,2.0)
	assert_eq(actor.packs,1)
