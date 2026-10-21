extends GutTest

var game: ArenaMatch
var station: Dictionary
var patient: ArenaRobot

func before_each() -> void:
	game = ArenaMatch.new()
	game.online = true
	game.authority = false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.set_process(false)
	game.map.start_map_assembly()
	game.map.assembly.seek(5.0,true)
	game.map.start_loadout()
	game.map.set_process(false)
	game.phase = "Active"
	for f in game.map.fixtures:
		if f.kind == "repair_station": station = f; break
	station.weld_fx.set_process(false)
	patient = game.add_robot(0,"Patient",0,true,"projector")
	patient.set_physics_process(false)
	patient.set_process(false)
	patient.weapon_vfx.set_physics_process(false)
	patient.weapon_vfx.set_process(false)
	game.local_robot = patient
	patient.protection = 0.0
	patient.ah = 40.0
	patient.ep = 12.0
	patient.position = station.point
	patient.listener.global_position = station.point
	await wait_physics_frames(3)

func claim() -> void:
	assert_true(game.map.start_repair(station,patient))
	assert_eq(station.occupant,patient)

func assert_released(refilled: bool, cooldown: float) -> void:
	assert_null(patient.repair)
	assert_null(station.occupant)
	assert_eq(station.cooldown,cooldown)
	assert_eq(patient.ah,100.0 if refilled else 40.0)
	assert_eq(patient.ep,100.0 if refilled else 12.0)
	for mesh in station.barrier_meshes: assert_false(mesh.visible)
	assert_false(station.weld_fx.glow.visible)
	assert_false(station.weld_fx.light.visible)
	assert_false(game.audio.loops.has("welding_"+station.id))

func test_phases_have_their_own_countdowns_and_dedicated_green_barrier():
	game.map.update_repair_status(station)
	game.map.update_repair_audio(station)
	assert_eq(game.map.repair_feedback(station).state,"ready")
	assert_true(game.audio.loops.has("repair_ready_"+station.id))
	assert_gt(station.barrier_meshes.size(),0)
	for mesh in station.barrier_meshes:
		assert_eq(mesh.material_override.shader,RepairBarrier.SHADER)
		assert_ne(mesh.material_override.shader,patient.surface_material.shader)
		assert_eq(mesh.material_override.get_shader_parameter("tint"),Color("60ef98"))
		assert_false(mesh.visible)
	game.reduced_motion=true
	game.map.update_repair_status(station)
	for mesh in station.barrier_meshes:assert_eq(mesh.material_override.get_shader_parameter("motion_enabled"),false)
	game.reduced_motion=false
	game.map.update_repair_status(station)
	for mesh in station.barrier_meshes:assert_eq(mesh.material_override.get_shader_parameter("motion_enabled"),true)
	claim()
	assert_false(game.audio.loops.has("repair_ready_"+station.id))
	assert_eq(game.map.repair_feedback(station).seconds,1.0)
	assert_false(game.map.repair_feedback(station).barrier)
	game.map.tick_repair(station,1.0)
	assert_eq(game.map.repair_feedback(station).seconds,5.0)
	assert_true(game.map.repair_feedback(station).barrier)
	for mesh in station.barrier_meshes: assert_true(mesh.visible)
	assert_true(game.audio.loops.has("welding_"+station.id))
	game.map.tick_repair(station,4.99)
	assert_eq(patient.ah,40.0)
	game.map.tick_repair(station,0.01)
	assert_eq(game.map.repair_feedback(station).seconds,1.0)
	assert_true(game.map.repair_feedback(station).barrier)
	assert_false(game.audio.loops.has("welding_"+station.id))
	assert_eq(game.audio.events.filter(func(e): return e.get("id", "") == "repair_start_stop").size(),2,"One start cue and one stop cue at deactivation")
	game.map.tick_repair(station,1.0)
	assert_released(true,60.0)
	assert_eq(game.map.repair_feedback(station).state,"recharging")
	assert_false(game.audio.loops.has("repair_ready_"+station.id),"Recharging is silent")

func test_repair_idles_hides_weapon_and_restores_equipment_and_ammo():
	patient.pickup_weapon = "rifle"
	patient.loaded = 32
	patient.packs = 2
	patient.equip("rifle")
	patient.reload_time = 0.5
	patient.pose("reload")
	claim()
	assert_eq(patient.anim_state,"common/idle")
	assert_false(patient.weapon_pose_visible)
	assert_false(patient.gun.visible)
	for collider in patient.gun.find_children("*","CollisionObject3D",true,false): assert_eq(collider.collision_layer,0)
	assert_eq(patient.reload_time,0.0)
	assert_eq(patient.loaded,32)
	assert_eq(patient.packs,2)
	assert_false(game.uses_first_person())
	game.map.tick_repair(station,7.0)
	assert_eq(patient.equipped,"rifle")
	assert_true(patient.weapon_pose_visible)
	assert_true(game.uses_first_person())
	assert_eq(patient.loaded,32)
	assert_eq(patient.packs,2)
	game.third_person = true
	game.update_view_models()
	assert_true(patient.gun.visible)

func test_finish_and_cancellation_abort_in_every_phase_without_late_refills():
	for canceled in [false,true]:
		for seconds in [0.5,2.0,6.5]:
			game.phase = "Active"
			game.map.reset_repairs()
			patient.ah = 40.0
			patient.ep = 12.0
			claim()
			game.map.tick_repair(station,seconds)
			game.finish(canceled)
			assert_released(seconds >= 6.0,0.0)
			game.map.tick_repair(station,20.0)
			assert_eq(patient.ah,100.0 if seconds >= 6.0 else 40.0)
			assert_false(game.audio.loops.has("repair_ready_"+station.id))

func test_explicit_geometry_invalidation_aborts_and_restore_requires_recharge():
	claim()
	game.map.tick_repair(station,2.0)
	game.map.set_repair_geometry_valid(station,false)
	assert_released(false,60.0)
	assert_eq(game.map.repair_feedback(station).state,"unavailable")
	game.map.set_repair_geometry_valid(station,true)
	assert_false(game.map.start_repair(station,patient))
	assert_eq(game.map.repair_feedback(station).state,"recharging")

func test_disabled_station_collision_aborts_and_rejects_a_new_claim():
	claim()
	assert_gt(station.geometry_colliders.size(),0)
	station.geometry_colliders[0].collision_layer = 0
	game.map.tick_repair(station,7.0)
	assert_released(false,60.0)
	station.cooldown = 0.0
	assert_false(game.map.start_repair(station,patient))

func test_moved_or_disabled_geometry_is_rejected_before_welding_completion():
	claim()
	game.map.tick_repair(station,5.0)
	station.node.position.x += 0.2
	game.map.tick_repair(station,1.0)
	assert_released(false,60.0)
	station.node.position.x -= 0.2
	game.map.set_repair_geometry_valid(station,true)
	game.map.reset_repairs()
	claim()
	station.trigger.monitoring = false
	game.map.tick_repair(station,7.0)
	assert_released(false,60.0)

func test_node_removal_and_freed_occupant_clear_both_sides_safely():
	claim()
	station.node.queue_free()
	game.map.tick_repair(station,7.0)
	assert_released(false,60.0)
	await wait_process_frames(2)
	assert_null(patient.repair)

func test_roster_departure_aborts_before_refill_and_disconnect_hook_cancels_match():
	claim()
	game.map.tick_repair(station,2.0)
	game.robots.erase(patient)
	game.map.tick_repair(station,4.0)
	assert_released(false,60.0)
	game.robots.append(patient)
	game.map.reset_repairs()
	claim()
	game.remove_robot(patient.robot_id)
	assert_null(station.occupant)
	assert_null(patient.repair)
	assert_eq(game.phase,"Finished")
	assert_true(game.result.canceled)
	assert_eq(patient.ah,40.0)

func test_abort_during_deactivation_retains_completed_refill():
	claim()
	game.map.tick_repair(station,6.25)
	game.map.set_repair_geometry_valid(station,false)
	assert_released(true,60.0)
	assert_eq(game.audio.events.filter(func(e): return e.get("id", "") == "repair_start_stop").size(),2,"An abort after welding does not play the stop recording twice")

func test_interruption_plays_supplied_stop_recording_and_ready_hum_returns_after_recharge():
	claim()
	game.map.tick_repair(station,2.0)
	game.map.abort_repair(station,"probe")
	assert_eq(game.audio.events.filter(func(e): return e.get("id", "") == "repair_start_stop").size(),2)
	game.map.abort_repair(station,"repeated_probe")
	assert_eq(game.audio.events.filter(func(e): return e.get("id", "") == "repair_start_stop").size(),2)
	assert_false(game.audio.loops.has("welding_"+station.id))
	assert_false(game.audio.loops.has("repair_ready_"+station.id))
	game.map.tick(60.0)
	game.map.update_repair_audio(station)
	assert_true(game.audio.loops.has("repair_ready_"+station.id))

func test_freed_occupant_does_not_leave_an_orphaned_station():
	claim()
	game.local_robot = null
	game.robots.erase(patient)
	patient.free()
	game.map.tick_repair(station,7.0)
	assert_null(station.occupant)
	assert_eq(station.cooldown,60.0)
	assert_false(game.audio.loops.has("welding_"+station.id))

func test_disconnect_during_deactivation_keeps_refill_and_recharges_if_match_continues():
	game.match_type = "CTF"
	for id in [1,2]:
		var robot: ArenaRobot = game.add_robot(id,"Peer%d" % id,id % 2,true,"projector")
		robot.set_physics_process(false)
		robot.set_process(false)
	claim()
	patient.carrying = 1
	game.flags[1].state = "carried"
	game.flags[1].carrier = patient.robot_id
	game.map.tick_repair(station,6.1)
	game.remove_robot(0)
	assert_null(patient.repair)
	assert_null(station.occupant)
	assert_eq(patient.ah,100.0)
	assert_eq(patient.ep,100.0)
	assert_eq(game.phase,"Active")
	assert_eq(station.cooldown,60.0)
	assert_eq(game.flags[1].state,"dropped","A disconnecting patient drops their CTF flag before roster resolution")
	assert_eq(game.flags[1].carrier,-1)
	assert_eq(patient.carrying,-1)

func test_death_shutdown_and_new_match_reset_release_without_partial_refill():
	claim()
	patient.alive = false
	game.map.tick_repair(station,1.0)
	assert_released(false,60.0)
	patient.alive = true
	game.map.reset_repairs()
	claim()
	game.map.shutdown()
	assert_released(false,0.0)
	game.map.shutting_down = false
	game.map.reset_repairs()
	assert_eq(game.map.repair_feedback(station).state,"ready")

func test_impact_moves_patient_during_activation_and_is_blocked_after_one_second():
	claim()
	patient.move_input = Vector2.ONE
	patient.apply_knockback(Vector3(5,1.5,0))
	var before := patient.position
	patient.tick_repair_motion(0.02)
	assert_gt(patient.position.x,before.x)
	assert_gt(patient.velocity.y,0.0)
	assert_eq(patient.ep,12.0)
	await wait_physics_frames(2)
	game.map.tick_repair(station,1.0)
	patient.tick_repair_motion(0.02)
	assert_eq(patient.knockback_velocity,Vector3.ZERO)
	assert_eq(patient.velocity,Vector3.ZERO)
	patient.apply_knockback(Vector3(11,4,0))
	assert_eq(patient.knockback_velocity,Vector3.ZERO)
	assert_eq(patient.velocity,Vector3.ZERO)
	assert_false(patient.can_take_damage(null))

func test_push_out_of_bay_aborts_activation_and_does_not_refill():
	claim()
	patient.apply_knockback(-station.node.global_basis.z * 11.0)
	for tick in 10: patient.tick_repair_motion(0.02)
	await wait_physics_frames(3)
	game.map.tick_repair(station,0.2)
	assert_released(false,60.0)

func test_same_patient_must_exit_before_reuse_and_feedback_reports_recharge():
	claim()
	game.map.tick_repair(station,7.0)
	patient.ah = 40
	assert_true(game.map.repair_hint(patient).contains("RECHARGING"))
	station.cooldown = 0.0
	assert_false(game.map.start_repair(station,patient))
	patient.position.x += 3.0
	await wait_physics_frames(3)
	game.map.tick(0.01)
	patient.position = station.point
	await wait_physics_frames(3)
	assert_true(game.map.start_repair(station,patient))
