extends GutTest

func fixture(type := "DM") -> ArenaMatch:
	var game:=ArenaMatch.new()
	game.online=true
	game.match_type=type
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority=false
	game.map.assembly.seek(5.0,true)
	game.phase="Active"
	game.goal=100
	for index in 3:
		var robot: ArenaRobot=game.add_robot(index,"Robot%d"%index,0 if index==0 else 1,true,"projector")
		robot.set_physics_process(false)
		robot.protection=0
		robot.global_position=Vector3(500+index*3,100,500)
		robot.last_safe=robot.global_position
	game.local_robot=game.robots[0]
	return game

func reset_victim(game: ArenaMatch) -> ArenaRobot:
	var victim: ArenaRobot=game.robots[1]
	if not victim.alive: game.spawn_robot(victim)
	victim.spawn_remaining=0
	victim.protection=0
	victim.global_position=Vector3(503,100,500)
	victim.last_safe=victim.global_position
	return victim

func fall(victim: ArenaRobot):
	victim.global_position.y=victim.arena_match.map.config.fall_boundary-10
	victim.simulate_movement(0.01)

func test_each_allowed_weapon_credits_real_boundary_death_without_a_drop():
	var game:=await fixture()
	var attacker: ArenaRobot=game.local_robot
	var count:=0
	for weapon in ["grenade_launcher","rocket_launcher","emp_gun"]:
		var victim:=reset_victim(game)
		assert_true(victim.hit(1,attacker,weapon))
		fall(victim)
		count+=1
		assert_false(victim.alive)
		assert_eq(attacker.kills,count)
		assert_eq(victim.deaths,count)
		assert_eq(game.feed_events[0].kind,"kill")
		assert_eq(game.feed_events[0].weapon,Arsenal.WEAPONS[weapon].title)
		assert_eq(game.feed_events[0].cause,"Fall off map")
		assert_eq(game.corpses.back().ep,0.0,"A credited fall still leaves no Energy Core")
		game.eliminate(victim,attacker,"Fall off map")
		assert_eq(attacker.kills,count,"One death cannot award twice")

func test_other_weapons_do_not_credit_falls_or_preserve_earlier_eligible_credit():
	var game:=await fixture()
	var victim: ArenaRobot=game.robots[1]
	for weapon in Arsenal.WEAPONS:
		if weapon in ["grenade_launcher","rocket_launcher","emp_gun"]: continue
		victim.ah=100
		assert_true(victim.hit(1,game.robots[0],"rocket_launcher"))
		assert_true(victim.hit(1,game.robots[2],weapon))
		assert_null(game.fall_killer(victim),"Only the last hit counts: "+weapon)
	fall(victim)
	assert_eq(game.robots[0].kills,0)
	assert_eq(game.robots[2].kills,0)
	assert_eq(game.feed_events[0].kind,"death")

func test_last_accepted_hit_can_be_shield_damage_and_survives_attacker_death():
	var game:=await fixture()
	var victim: ArenaRobot=game.robots[1]
	victim.sh=100
	assert_true(victim.hit(1,game.robots[0],"grenade_launcher"))
	assert_true(victim.hit(1,game.robots[2],"emp_gun"))
	assert_gt(victim.sh,0.0,"A hit absorbed mostly by the shield still qualifies")
	assert_lt(victim.sh,100.0)
	game.robots[2].alive=false
	game.elapsed=100
	fall(victim)
	assert_eq(game.robots[0].kills,0)
	assert_eq(game.robots[2].kills,1,"The last hitter can receive posthumous credit during this life")

func test_rejected_hits_do_not_replace_credit_and_self_damage_cannot_award_it():
	var game:=await fixture("TDM")
	var victim: ArenaRobot=game.robots[1]
	assert_true(victim.hit(1,game.robots[0],"rocket_launcher"))
	assert_false(victim.hit(1,game.robots[2],"rifle"),"Friendly fire is rejected")
	assert_false(victim.hit(0,game.robots[0],"rifle"))
	victim.protection=1
	assert_false(victim.hit(1,game.robots[0],"rifle"))
	victim.protection=0
	assert_eq(game.fall_killer(victim),game.robots[0])
	assert_true(victim.hit(1,victim,"grenade_launcher"))
	fall(victim)
	assert_eq(game.robots[0].kills,0)
	assert_eq(game.team_scores,[0,0])

func test_respawn_clears_credit_and_power_death_does_not_use_it():
	var game:=await fixture()
	var victim: ArenaRobot=game.robots[1]
	victim.hit(1,game.robots[0],"emp_gun")
	game.eliminate(victim,null,"Power depleted")
	assert_eq(game.local_robot.kills,0)
	victim=reset_victim(game)
	assert_eq(victim.last_hit_robot_id,-1)
	assert_eq(victim.last_hit_weapon,"")
	fall(victim)
	assert_eq(game.local_robot.kills,0)

func test_team_scores_and_gun_game_progression_use_the_credited_kill():
	for type in ["TDM","CTF","GUNGAME","ELIMINATION"]:
		var game:=await fixture(type)
		var victim: ArenaRobot=game.robots[1]
		var attacker: ArenaRobot=game.local_robot
		attacker.alive=false
		if type=="GUNGAME": game.advance_gun_game(attacker)
		attacker.alive=true
		var previous:=attacker.gun_game_weapon
		victim.hit(20,game.robots[2],"rifle") if type in ["DM","GUNGAME","ELIMINATION"] else victim.hit(20,attacker,"rifle")
		victim.hit(1,attacker,"rocket_launcher")
		fall(victim)
		assert_eq(attacker.kills,1)
		assert_eq(game.team_scores,[1,0] if type=="TDM" else [0,0])
		assert_eq(game.feed_events[0].killer_team,0)
		if type in ["GUNGAME","ELIMINATION"]: assert_eq(game.robots[2].assists,1,"Recent contributors keep the ordinary assist rule")
		if type=="GUNGAME": assert_ne(attacker.gun_game_weapon,previous)
		if type=="ELIMINATION": assert_eq(victim.lives_remaining(),4)

func test_actual_grenade_direct_and_splash_contacts_both_record_the_shooter():
	var game:=await fixture()
	game.authority=true
	var direct: ArenaRobot=game.robots[1]
	var splash: ArenaRobot=game.robots[2]
	var grenade:=BallisticProjectile.new()
	grenade.game=game
	grenade.weapon="grenade_launcher"
	grenade.profile=Arsenal.WEAPONS.grenade_launcher
	grenade.shooter=game.local_robot
	grenade.velocity=Vector3.RIGHT*15
	game.add_child(grenade)
	grenade.set_physics_process(false)
	grenade.impact({"collider":direct,"position":direct.eye(),"normal":Vector3.UP})
	game.authority=false
	assert_eq(game.fall_killer(direct),game.local_robot)
	assert_eq(game.fall_killer(splash),game.local_robot)
	fall(direct)
	fall(splash)
	assert_eq(game.local_robot.kills,2)
	var feed:=HudKillFeed.format_event(game.feed_events[0],"DM",game.team_colors)
	assert_true(feed.contains("knocked"))
	assert_true(feed.contains("out of the arena"))
