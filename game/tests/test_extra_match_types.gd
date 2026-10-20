extends GutTest

func match_case(type: String, arena := "skyfall") -> ArenaMatch:
	var game:=ArenaMatch.new()
	game.online=true
	game.match_type=type
	game.map_id=arena
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority=false
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0,true)
	game.phase="Active"
	game.goal=50
	for index in 3:
		var robot: ArenaRobot=game.add_robot(index,"Robot%d"%index,index%2,true,"projector")
		robot.set_physics_process(false)
		robot.global_position=Vector3(index*2,2,0)
		robot.last_safe=robot.global_position
	game.local_robot=game.robots[0]
	return game

func test_five_lives_and_instant_action_stops_at_local_elimination():
	var game:=await match_case("ELIMINATION")
	var victim: ArenaRobot=game.local_robot
	var opponent: ArenaRobot=game.robots[1]
	assert_true(victim.enemy(game.robots[2]),"Same-zone robots are opponents in free-for-all")
	for death in 4:
		game.eliminate(victim,opponent,"rifle")
		assert_eq(victim.lives_remaining(),4-death)
		assert_false(victim.eliminated())
		assert_eq(game.phase,"Active")
		game.spawn_robot(victim)
		assert_true(victim.alive,"The first four deaths allow respawning")
	game.online=false
	game.eliminate(victim,null,"Power depleted")
	assert_true(victim.eliminated())
	game.spawn_robot(victim)
	assert_false(victim.alive,"No spawn path can restore a fifth-death robot")
	assert_eq(game.phase,"Finished")
	assert_eq(game.result.title,"Eliminated")
	assert_true(game.result.early_exit)
	assert_false(game.local_won())
	assert_eq(game.result.winner_ids.size(),0,"An unfinished bot contest has no declared winner")
	assert_true(game.audio.events.any(func(event): return event.get("asset","")=="speech/announcer/eliminated"))
	assert_false(game.audio.events.any(func(event): return event.get("asset","")=="speech/announcer/match_won"))

func test_elimination_timeout_goal_and_last_survivor():
	var game:=await match_case("ELIMINATION")
	game.robots[0].deaths=1
	game.robots[0].kills=3
	game.robots[1].deaths=2
	game.robots[1].kills=8
	game.robots[2].deaths=5
	game.time_limit=10
	game.elapsed=10
	game.authority=true
	game._physics_process(0.01)
	game.authority=false
	assert_eq(game.result.winner_ids,[0],"Lives rank above kills at the time limit")
	assert_true(game.local_won())
	game.phase="Active"
	game.goal=8
	game.finish()
	assert_eq(game.result.winner_ids,[1],"The configured kill goal can end Elimination")
	game.phase="Active"
	game.goal=50
	game.time_limit=1000
	game.robots[1].deaths=5
	game.authority=true
	game._physics_process(0.01)
	game.authority=false
	assert_eq(game.phase,"Finished","The final survivor ends the match")
	assert_eq(game.result.winner_ids,[0])

func test_eliminated_online_robot_stays_dead_and_only_receives_its_announcement():
	var game:=await match_case("ELIMINATION")
	game.replicating=true
	game.authority=true
	game.robots[1].deaths=4
	game.eliminate(game.robots[1],game.local_robot,"rifle")
	game.authority=false
	assert_eq(game.phase,"Active","Online survivors continue playing")
	game.spawn_robot(game.robots[1])
	assert_false(game.robots[1].alive)
	game.robots[1].restore_network(game.robots[1].network_state())
	assert_true(game.robots[1].eliminated(),"Replicated death totals retain elimination state")
	var events: Array=game.presentation_events.filter(func(event): return event.kind=="caption" and event.text=="Eliminated")
	assert_eq(events.size(),1)
	assert_eq(events[0].recipient,1)
	game.replicating=false
	assert_false(game.callouts.publish("Eliminated","Announcer",-1,true,Vector3.INF,1))
	game.local_robot=game.robots[1]
	assert_true(game.callouts.publish("Eliminated","Announcer",-1,true,Vector3.INF,1))
	assert_true(game.audio.events.any(func(event): return event.get("asset","")=="speech/announcer/eliminated"))

func test_weapon_cycles_are_unique_and_do_not_repeat_at_boundary():
	var game:=ArenaMatch.new()
	autofree(game)
	game.match_type="GUNGAME"
	game.rng.seed=123
	var robot:=ArenaRobot.new()
	autofree(robot)
	robot.alive=false
	var last:=""
	for cycle in 4:
		var seen: Array[String]=[]
		for index in Arsenal.WEAPONS.size():
			game.advance_gun_game(robot)
			assert_ne(robot.gun_game_weapon,last)
			assert_false(robot.gun_game_weapon in seen)
			seen.append(robot.gun_game_weapon)
			last=robot.gun_game_weapon
		assert_eq(seen.size(),10)

func test_gun_game_kill_changes_equipment_and_death_preserves_assignment():
	var game:=await match_case("GUNGAME")
	var robot: ArenaRobot=game.local_robot
	game.advance_gun_game(robot)
	var first:=robot.equipped
	assert_eq(robot.owned_weapons,[first])
	assert_false(robot.can_pickup_weapon("rifle"))
	game.eliminate(game.robots[1],robot,"rifle")
	await wait_process_frames(1)
	assert_ne(robot.equipped,first)
	assert_eq(robot.equipped,robot.gun_game_weapon)
	assert_eq(robot.owned_weapons,[robot.equipped])
	var assigned:=robot.gun_game_weapon
	var remaining:=robot.gun_game_cycle.duplicate()
	game.eliminate(robot,null,"Power depleted")
	game.spawn_robot(robot)
	assert_true(robot.alive)
	assert_eq(robot.equipped,assigned)
	assert_eq(robot.gun_game_cycle,remaining)
	robot.gun_game_weapon="rifle"
	game.equip_gun_game(robot)
	assert_eq(robot.loaded,int(Arsenal.WEAPONS.rifle.capacity))
	robot.spawn_remaining=0
	robot.protection=0
	robot.select_weapon("pistol")
	assert_eq(robot.equipped,"rifle")
	robot.loaded=0
	robot.packs=0
	robot.handle_empty_weapon()
	assert_eq(robot.equipped,"rifle","Empty guns must not bypass the assigned cycle")
	assert_true(robot.pickup_ammo("rifle"))
	robot.handle_empty_weapon()
	assert_gt(robot.reload_time,0.0)

func test_gun_game_keeps_ammo_and_closed_holders_without_cradles_on_both_maps():
	for arena in ["skyfall","faceoff"]:
		var game:=await match_case("GUNGAME",arena)
		game.map.start_loadout()
		assert_false(game.map.fixtures.any(func(fixture): return fixture.kind=="weapon"))
		var expected_ammo: int=game.map.markers.filter(func(marker): return marker.role=="ammo").size()
		assert_eq(game.map.fixtures.filter(func(fixture): return fixture.kind=="ammo").size(),expected_ammo)
		var holders:=game.map.find_children("DisabledWeaponHolder*","Node3D",true,false)
		assert_gt(holders.size(),0)
		game.map.start_loadout()
		assert_eq(game.map.find_children("DisabledWeaponHolder*","Node3D",true,false).size(),holders.size(),"Repeated loadout setup must not duplicate closed holders")
		for holder in holders:
			var motion: PropMotion=game.map.machinery.filter(func(item): return item.asset==holder)[0]
			assert_eq(motion.channels.main.clip,"retract")
			assert_almost_eq(motion.channels.main.time,motion.channels.main.player.get_animation("retract").length,0.001)
			assert_gt(holder.find_children("*","StaticBody3D",true,false).size(),0)

func test_victory_speech_is_only_for_local_winner():
	var game:=await match_case("DM")
	game.robots[1].kills=5
	game.finish()
	assert_false(game.audio.events.any(func(event): return event.get("asset","")=="speech/announcer/match_won"))
	game.phase="Active"
	game.local_robot=game.robots[1]
	game.finish()
	assert_true(game.audio.events.any(func(event): return event.get("asset","")=="speech/announcer/match_won"))

func test_reliable_victory_audio_does_not_depend_on_final_snapshot_arrival():
	var game:=await match_case("DM")
	game.replicating=true
	var transport:=OnlineTransport.new()
	transport.game=game
	transport.closed=true
	add_child_autofree(transport)
	var event:={"kind":"caption","text":"Robot0 wins","speaker":"Announcer","team":-1,"critical":true,"point":Vector3.INF,"winner_ids":[0]}
	assert_eq(game.phase,"Active")
	assert_true(game.result.is_empty())
	transport.apply_presentation(event)
	assert_true(game.audio.events.any(func(item): return item.get("asset","")=="speech/announcer/match_won"))
