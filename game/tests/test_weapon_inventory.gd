extends GutTest

func pilot() -> ArenaRobot:
	var game := ArenaMatch.new()
	game.online=true
	game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.phase="Active"
	var actor: ArenaRobot = game.add_robot(0,"Pilot",0,true,"projector")
	actor.set_process(false)
	actor.set_physics_process(false)
	actor.weapon_vfx.set_physics_process(false)
	actor.protection=0
	actor.spawn_remaining=0
	return actor

func test_collect_all_weapons_and_switch_without_losing_any_ammo():
	var actor := await pilot()
	for id in Arsenal.WEAPONS:
		if id=="pistol": continue
		assert_true(actor.take_weapon(id),id)
		assert_eq(actor.equipped,id)
		actor.loaded=7
		assert_true(actor.pickup_ammo(id))
	assert_eq(actor.owned_weapons.size(),10)
	for id in actor.owned_weapons:
		actor.select_weapon(id)
		if id=="pistol": continue
		assert_eq(actor.loaded,7,id+" retains its loaded rounds")
		assert_eq(actor.packs,1,id+" retains its spare pack")
	assert_eq(actor.cycle_weapon(1),"pistol")
	actor.select_weapon("pistol")
	assert_eq(actor.cycle_weapon(-1),actor.owned_weapons[-1])

func test_extinguished_weapon_rigs_can_be_replaced_within_the_same_frame():
	var actor := await pilot()
	for id in Arsenal.WEAPONS:
		actor.equip(id)
		Assets.paint(actor.gun,actor.tint,actor.armor_secondary,actor.head,true,actor.upper_body)
		var retired: WeakRef = weakref(actor.gun)
		actor.equip("pistol")
		assert_null(retired.get_ref(),id+" releases the extinguished rig immediately")
		assert_true(is_instance_valid(actor.gun),"Replacement weapon remains usable")
		assert_not_null(Assets.socket(actor.gun,"RightHandSocket"))

func test_precollect_unowned_ammo_full_pack_cap_and_bank_on_acquisition():
	var actor := await pilot()
	for id in Arsenal.WEAPONS:
		if id=="pistol": continue
		for pack in 4: assert_true(actor.pickup_ammo(id),id)
		assert_false(actor.pickup_ammo(id),"A fifth full pack is rejected")
		assert_false(id in actor.owned_weapons,"Ammo alone cannot grant a gun")
		assert_true(actor.take_weapon(id))
		assert_eq(actor.loaded,int(Arsenal.WEAPONS[id].capacity))
		assert_eq(actor.packs,3,"The bank supplies one loaded pack at the total cap")
	assert_false(actor.pickup_ammo("pistol"))
	assert_false(actor.pickup_ammo("unknown"))

func test_duplicate_refills_only_its_loaded_pack_and_preserves_active_weapon():
	var actor := await pilot()
	actor.take_weapon("rifle")
	actor.loaded=17
	actor.packs=2
	actor.take_weapon("rocket_launcher")
	actor.loaded=3
	assert_true(actor.take_weapon("rifle"))
	assert_eq(actor.equipped,"rocket_launcher")
	assert_eq(actor.loaded,3)
	assert_eq(actor.ammo_for("rifle"),{"loaded":100,"packs":2})
	assert_eq(actor.owned_weapons,["pistol","rifle","rocket_launcher"])
	assert_false(actor.take_weapon("rifle"),"A full loaded pack leaves the pickup available")
	actor.select_weapon("rifle")
	actor.loaded=0
	actor.packs=4
	assert_true(actor.take_weapon("rifle"))
	assert_eq(actor.loaded+actor.packs*100,400)

func test_empty_fallback_prefers_immediate_previous_with_ammo_else_pistol():
	var actor := await pilot()
	actor.take_weapon("rifle")
	actor.loaded=31
	actor.take_weapon("rocket_launcher")
	actor.loaded=0
	actor.handle_empty_weapon()
	assert_eq(actor.equipped,"rifle")
	assert_eq(actor.loaded,31)
	actor.take_weapon("minigun")
	actor.ammo_entry("rifle").loaded=0
	actor.loaded=0
	actor.handle_empty_weapon()
	assert_eq(actor.equipped,"pistol")
	assert_true("minigun" in actor.owned_weapons)

func test_previous_with_spares_reloads_and_manual_selection_cannot_cancel_reload():
	var actor := await pilot()
	actor.take_weapon("rifle")
	actor.loaded=0
	actor.packs=1
	actor.take_weapon("rocket_launcher")
	actor.loaded=0
	actor.handle_empty_weapon()
	assert_eq(actor.equipped,"rifle")
	assert_eq(actor.reload_time,2.0)
	actor.select_weapon("pistol")
	assert_eq(actor.equipped,"rifle")
	actor.arena_match.authority=true
	actor._physics_process(2.0)
	actor.arena_match.authority=false
	assert_eq(actor.loaded,100)
	assert_eq(actor.packs,0)
	assert_eq(actor.ammo_for("rocket_launcher").loaded,0)

func test_same_weapon_pickup_during_reload_refills_without_spending_spare():
	var actor := await pilot()
	actor.take_weapon("rifle")
	actor.loaded=8
	actor.packs=1
	actor.start_reload()
	assert_eq(actor.reload_time,2.0)
	assert_true(actor.take_weapon("rifle"))
	assert_eq(actor.reload_time,0.0)
	assert_eq(actor.loaded,100)
	assert_eq(actor.packs,1)

func test_pickup_keeps_a_scheduled_last_rocket_before_equipping_new_weapon():
	var actor := await pilot()
	actor.take_weapon("rocket_launcher")
	actor.loaded=1
	actor.wants_fire=true
	actor.arena_match.combat.trigger(actor,.01)
	assert_true(actor.take_weapon("rifle"))
	assert_eq(actor.equipped,"rocket_launcher")
	assert_eq(actor.queued_weapon,"rifle")
	actor.weapon_vfx._physics_process(.04)
	var rockets: Array = actor.arena_match.get_children().filter(func(n): return n is ArenaProjectile)
	assert_eq(rockets.size(),1)
	assert_eq(rockets[0].weapon,"rocket_launcher")
	actor.wants_fire=false
	actor.arena_match.authority=true
	actor._physics_process(.01)
	actor.arena_match.authority=false
	assert_eq(actor.equipped,"rifle")
	assert_eq(actor.loaded,100)

func test_online_inventory_roundtrip_is_deep_and_preserves_reload_and_previous():
	var actor := await pilot()
	actor.take_weapon("rifle")
	actor.loaded=11
	actor.pickup_ammo("emp_gun")
	actor.take_weapon("rocket_launcher")
	actor.loaded=0
	actor.packs=1
	actor.start_reload()
	var state: Dictionary = actor.network_state()
	actor.reset_inventory()
	actor.equip("pistol")
	actor.restore_network(state,true)
	assert_eq(actor.owned_weapons,["pistol","rifle","rocket_launcher"])
	assert_eq(actor.ammo_for("rifle").loaded,11)
	assert_eq(actor.ammo_for("emp_gun").packs,1)
	assert_eq(actor.previous_weapon,"rifle")
	assert_eq(actor.reload_time,2.0)
	actor.ammo_entry("rifle").loaded=3
	assert_eq(state.ammo_inventory.rifle.loaded,11,"Snapshot dictionaries cannot alias live inventory")
	var mount := Node3D.new()
	actor.arena_match.add_child(mount)
	mount.global_position=Vector3(0,100,0)
	actor.arena_match.map.spawns.append({"id":"inventory-test","team":0,"point":mount.global_position,"node":mount,"mount":mount})
	actor.arena_match.spawn_robot(actor)
	assert_eq(actor.owned_weapons,["pistol"])
	assert_eq(actor.ammo_inventory,{})
	assert_eq(actor.queued_weapon,"")
	assert_eq(actor.previous_weapon,"pistol")

func test_online_numbered_slots_are_validated_and_never_grant_unowned_guns():
	var actor := await pilot()
	actor.take_weapon("rifle")
	actor.take_weapon("rocket_launcher")
	var command := {"generation":"match","seq":1,"move":Vector2.ZERO,"yaw":0.0,"pitch":0.0,"walk":false,"sprint":false,"crouch":false,"fire":false,"secondary":false,"held":false,"jump":false,"release":false,"reload":false,"slot":"slot:2"}
	OnlineInput.apply(actor,command)
	assert_eq(actor.equipped,"rifle")
	for slot in ["slot:0","slot:11","slot:01","slot:-1","slot:rifle"]:
		command.slot=slot
		assert_false(OnlineInput.valid(command,"match",0),slot)
	command.slot="slot:10"
	assert_true(OnlineInput.valid(command,"match",0))
	OnlineInput.apply(actor,command)
	assert_eq(actor.equipped,"rifle","An absent index cannot equip or grant a gun")
	command.slot="slot:3"
	actor.protection=1
	OnlineInput.apply(actor,command)
	assert_eq(actor.equipped,"rifle")
	actor.protection=0
	actor.reload_time=1
	OnlineInput.apply(actor,command)
	assert_eq(actor.equipped,"rifle")
	actor.reload_time=0
	OnlineInput.apply(actor,command,true)
	assert_eq(actor.equipped,"rifle","Client prediction cannot grant an authoritative switch")
	OnlineInput.apply(actor,command)
	assert_eq(actor.equipped,"rocket_launcher")

func test_slot_grid_scales_caps_width_and_right_aligns_both_rows():
	for screen in [640.0,1280.0,1920.0,2560.0]:
		var area := Vector2(screen*.4-32,148)
		for count in range(1,11):
			var slots := WeaponReadout.slot_rects(count,area,screen)
			assert_eq(slots.size(),count)
			for index in count:
				assert_lte(slots[index].size.x,screen*.15)
				assert_true(Rect2(Vector2.ZERO,area).encloses(slots[index]))
				for other in range(index+1,count): assert_false(slots[index].intersects(slots[other]))
			assert_almost_eq(slots[mini(count,5)-1].end.x,area.x,.001)
			if count>5: assert_almost_eq(slots[-1].end.x,area.x,.001)
	assert_eq(WeaponReadout.slot_rects(11,Vector2(700,148),1920).size(),10)

func test_number_keys_cover_third_through_tenth_slot_without_key_repeat():
	var app = load("res://scripts/core/app.gd")
	for index in range(2,10):
		var event := InputEventKey.new()
		event.pressed=true
		event.keycode=KEY_1+index if index<9 else KEY_0
		assert_eq(app.numbered_slot(event),index)
		event.echo=true
		assert_eq(app.numbered_slot(event),-1)

func test_continuous_fire_finishes_funded_interval_before_previous_weapon_fallback():
	var actor := await pilot()
	actor.take_weapon("rifle")
	actor.loaded=12
	actor.take_weapon("lightning_gun")
	actor.loaded=1
	actor.wants_fire=true
	actor.arena_match.combat.trigger(actor,.1)
	assert_eq(actor.loaded,0)
	actor.arena_match.combat.trigger(actor,.1)
	assert_eq(actor.equipped,"lightning_gun","The last ammo interval is still funded")
	actor.arena_match.combat.trigger(actor,.41)
	assert_eq(actor.equipped,"rifle")
	assert_eq(actor.loaded,12)
	assert_eq(actor.ammo_for("lightning_gun").loaded,0)

func test_live_pickup_predicates_restock_only_after_a_successful_collection():
	var actor := await pilot()
	var map: ArenaMap = actor.arena_match.map
	var notices: Array[String] = []
	actor.arena_match.message.connect(func(text): notices.append(text))
	var payload := Node3D.new()
	map.add_child(payload)
	var fixture := {"kind":"ammo","weapon":"emp_gun","ready":true,"cooldown":0.0,"payload":payload}
	actor.protection=1
	assert_false(map.can_collect(fixture,actor))
	actor.protection=0
	assert_true(map.can_collect(fixture,actor),"Unowned weapon ammo is eligible")
	map.collect(fixture,actor)
	assert_eq(actor.ammo_for("emp_gun").packs,1)
	assert_eq(notices.back(),"EMP gun ammo acquired")
	assert_eq(fixture.cooldown,60)
	assert_false(fixture.ready)
	assert_false(payload.visible)
	assert_false(map.can_collect(fixture,actor))
	fixture.kind="weapon"
	fixture.weapon="rifle"
	fixture.ready=true
	fixture.cooldown=0
	payload.show()
	map.collect(fixture,actor)
	assert_eq(notices.back(),"Rifle acquired")
	assert_eq(actor.equipped,"rifle")
	fixture.ready=true
	fixture.cooldown=0
	payload.show()
	map.collect(fixture,actor)
	assert_eq(fixture.cooldown,0,"A rejected full magazine leaves the pickup ready")
	assert_true(payload.visible)
	actor.loaded=9
	assert_true(map.can_collect(fixture,actor))
	map.collect(fixture,actor)
	assert_eq(actor.loaded,100)
	assert_eq(fixture.cooldown,60)

func test_uninitialized_hud_dimensions_produce_no_invalid_slots():
	assert_eq(WeaponReadout.slot_rects(7,Vector2.ZERO,0).size(),0)
	assert_eq(WeaponReadout.slot_rects(7,Vector2(4,4),1920).size(),0)

class InventoryProbe extends ArenaRobot:
	func equip(id: String) -> void:
		previous_weapon=equipped
		equipped=id

func test_tenth_slot_is_accepted_and_eleventh_rejected_with_existing_refill_allowed():
	var actor := InventoryProbe.new()
	autofree(actor)
	var temporary: Array[String] = []
	for index in 4:
		var id := "future_%d" % index
		temporary.append(id)
		Arsenal.WEAPONS[id]={"capacity":20}
	for id in Arsenal.WEAPONS:
		if id=="pistol": continue
		var allowed := actor.owned_weapons.size()<10
		assert_eq(actor.take_weapon(id),allowed)
	assert_eq(actor.owned_weapons.size(),10)
	assert_false(actor.take_weapon(temporary[-1]))
	actor.ammo_entry("rifle").loaded=0
	assert_true(actor.take_weapon("rifle"),"A full inventory still permits a refill")
	assert_true(actor.pickup_ammo(temporary[-1]),"Banked ammo needs no weapon slot")
	for id in temporary: Arsenal.WEAPONS.erase(id)

func test_releasing_after_last_shot_still_falls_back_after_its_delayed_launch():
	var actor := await pilot()
	actor.take_weapon("rifle")
	actor.loaded=12
	actor.take_weapon("rocket_launcher")
	actor.loaded=1
	actor.wants_fire=true
	actor.arena_match.combat.trigger(actor,.01)
	actor.wants_fire=false
	actor.arena_match.combat.trigger(actor,.01)
	assert_eq(actor.equipped,"rocket_launcher")
	actor.weapon_vfx._physics_process(.04)
	actor.arena_match.combat.trigger(actor,.01)
	assert_eq(actor.equipped,"rifle")
	assert_eq(actor.loaded,12)

func test_selecting_current_slot_keeps_rig_and_cancels_a_queued_switch():
	var actor := await pilot()
	var original := actor.gun
	actor.select_weapon("pistol")
	assert_same(actor.gun,original)
	actor.take_weapon("rocket_launcher")
	actor.take_weapon("rifle")
	original=actor.gun
	actor.weapon_vfx.schedule(.5,func(): pass)
	actor.select_weapon("rocket_launcher")
	assert_eq(actor.queued_weapon,"rocket_launcher")
	actor.select_weapon("rifle")
	assert_eq(actor.queued_weapon,"")
	assert_same(actor.gun,original)
