extends GutTest

func test_nonlethal_hits_apply_damage_immediately_and_react_on_physics_sample():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	var victim: ArenaRobot = game.add_robot(0,"Reaction",0,true,"projector")
	victim.set_physics_process(false)
	victim.set_process(false)
	game.phase = "Active"
	victim.protection = 0
	victim.spawn_remaining = 0
	victim.sh = 0
	victim.global_position = Vector3(200,100,0)
	victim.update_aim_pose(0)
	var initial: Array[Transform3D] = []
	for bone in victim.skeleton.get_bone_count(): initial.append(victim.skeleton.get_bone_pose(bone))
	for impact in 4: assert_true(victim.hit(5,null,"pistol"))
	assert_eq(victim.ah,80.0,"All hits apply immediately")
	for bone in initial.size(): assert_eq(victim.skeleton.get_bone_pose(bone),initial[bone],"No zero-weight pose resampling between hits")
	victim._physics_process(1.0/60.0)
	assert_gt(victim.hit_pose.saved.size(),0,"Authored reaction is applied at the next physics sample")
	assert_almost_eq(victim.hit_flash,0.2-1.0/60.0,0.00001)
	assert_true(victim.alive)

func test_lethal_lunar_contact_keeps_physical_debris_and_death_camera():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	game.set_physics_process(false)
	var floor := StaticBody3D.new()
	floor.set_meta("lethal_surface",true)
	game.add_child(floor)
	# Keep the isolated test floor above the map's lunar terrain.
	floor.position = Vector3(200,19.5,0)
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size=Vector3(8,1,8)
	shape.shape=box
	floor.add_child(shape)
	await wait_physics_frames(2)
	var victim: ArenaRobot = game.add_robot(0,"Lunar impact",0,true,"projector")
	game.local_robot=victim
	game.phase="Active"
	victim.global_position=Vector3(200,20.01,0)
	victim.velocity=Vector3(0,-20,0)
	game.eliminate(victim,null,"Fall off map")
	assert_false(game.corpses[0].falling_out)
	assert_false(game.local_fall_death)
	var debris := game.corpses[0].node as RobotDebris
	assert_not_null(debris,"Lethal terrain scatters physical body assemblies")
	if debris == null: return
	assert_null(debris.find_child("RuntimeAnimator",true,false),"Debris does not replay a standing death clip")
	assert_eq(debris.bodies.size(),RobotDebris.GROUPS.size())
	assert_almost_eq(victim.respawn_time,4.0,0.02,"Lunar debris retains the four-second death presentation")
	assert_almost_eq(game.death_view_remaining,4.0,0.02)
	assert_almost_eq(game.corpses[0].point.y,20.0,0.002)
	var initial: Dictionary = debris.snapshot().bodies
	for body: RigidBody3D in debris.bodies.values():
		assert_eq(body.collision_mask,1,"Assemblies collide with the contacted terrain")
		assert_eq(body.collision_layer,0,"Cosmetic debris cannot block living robots")
	await wait_seconds(0.15)
	assert_true(debris.bodies.values().any(func(body):return not body.global_transform.is_equal_approx(initial[body.name].transform)),"Physical debris advances after contact")
	game._process(0.0)
	assert_eq(game.camera_rig.active_view,"death")
	assert_almost_eq(game.camera_rig.focus_anchors.death.global_position.y,debris.focus_position().y,0.001,"Death camera follows the scattered chest")
	assert_eq(game.corpses[0].ep,0.0)
	game.tick_drops(3.9)
	assert_eq(game.corpses.size(),1,"Debris remains through the death presentation")
	game.tick_drops(0.11)
	assert_true(game.corpses.is_empty())
	assert_true(game.drops.is_empty(),"Lethal terrain never leaves an Energy Core")

func test_direction_headshot_and_crouch_conditions_play_authored_death_variants():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	game.phase = "Active"
	var victim: ArenaRobot = game.add_robot(0,"Victim",0,true,"projector")
	var killer: ArenaRobot = game.add_robot(1,"Attacker",1,true,"projector")
	victim.set_process(false)
	victim.set_physics_process(false)
	killer.set_process(false)
	killer.set_physics_process(false)
	game.local_robot = null
	for example in [
		["pistol",Vector3.FORWARD,false,"death_front"],
		["pistol",Vector3.BACK,false,"death_back"],
		["pistol",Vector3.RIGHT,false,"death_right"],
		["rifle_headshot",Vector3.FORWARD,false,"death_front_headshot"],
		["rifle_headshot",Vector3.BACK,false,"death_back_headshot"],
		["rifle_headshot",Vector3.FORWARD,true,"death_crouching_headshot"]]:
		victim.alive = true
		victim.yaw = 0.7
		victim.crouched = example[2]
		victim.global_position = Vector3(200,100,0)
		killer.global_position = victim.global_position + Basis(Vector3.UP,victim.yaw)*example[1]*5.0
		game.eliminate(victim,killer,example[0])
		var corpse: Node3D = game.corpses[0].node
		var animator := corpse.find_child("RuntimeAnimator",true,false) as AnimationPlayer
		assert_eq(animator.current_animation,"common_"+example[3],"Actual corpse clip follows lethal condition")
		assert_true(animator.is_playing(),"Ordinary deaths retain their authored animation")
		animator.advance(0.1)
		assert_gt(animator.current_animation_position,0.0)
		game.corpses.clear()
		corpse.queue_free()
		await wait_process_frames(1)

func test_death_corpse_plays_the_authored_clip_and_camera_frames_it():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	var victim: ArenaRobot = game.add_robot(0, "Victim", 0, true, "projector")
	game.local_robot = victim
	game.phase = "Active"
	victim.global_position = Vector3(0, 2, 0)
	victim.last_safe = victim.global_position
	game.eliminate(victim, null, "pistol")
	assert_eq(game.corpses.size(), 1)
	var corpse: Node3D = game.corpses[0].node
	var animator := corpse.find_child("RuntimeAnimator", true, false) as AnimationPlayer
	assert_true(corpse.visible)
	assert_not_null(animator)
	if animator == null: return
	assert_eq(animator.current_animation, "common_death_front")
	assert_eq(animator.callback_mode_process, AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE)
	assert_almost_eq(victim.respawn_time, animator.current_animation_length + 1.0, 0.02)
	var skeleton := Assets.find(corpse, "Skeleton3D") as Skeleton3D
	var corpse_weapon_mount := skeleton.find_children("*", "BoneAttachment3D", true, false).filter(func(node): return node.get_child_count() > 0)
	var native := Assets.model("characters", victim.character.model)
	var native_skeleton := Assets.find(native, "Skeleton3D") as Skeleton3D
	assert_eq(corpse_weapon_mount.size(), native_skeleton.find_children("*", "BoneAttachment3D", true, false).filter(func(node): return node.get_child_count() > 0).size(), "The corpse retains native sockets without live hit bodies or a weapon mount")
	native.free()
	assert_true(corpse.find_children("*", "CollisionObject3D", true, false).is_empty())
	assert_false(victim.weapon_pose_visible)
	var initial: Array[Transform3D] = []
	for bone in skeleton.get_bone_count(): initial.append(skeleton.get_bone_pose(bone))
	await wait_seconds(0.35)
	var animated := false
	for bone in skeleton.get_bone_count():
		if initial[bone] != skeleton.get_bone_pose(bone): animated = true
	assert_true(animated, "The visible corpse skeleton must advance through the death clip")
	assert_gt(game.death_view_remaining, 0.0, "The local death camera remains active during the clip")
	assert_gt(game.camera.global_position.distance_to(corpse.global_position), 1.0)
	game.tick_drops(animator.current_animation_length + 1.0)
	assert_eq(game.corpses.size(), 0, "The corpse disappears after the animation and one-second hold")

func test_local_death_holds_third_person_for_one_second_after_animation():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	var victim: ArenaRobot = game.add_robot(0, "Victim", 0, true, "projector")
	var killer: ArenaRobot = game.add_robot(1, "Killer", 1, true, "sentinel")
	game.local_robot = victim
	game.phase = "Active"
	victim.global_position = Vector3(0, 2, 0)
	victim.last_safe = victim.global_position
	killer.global_position = Vector3(2, 2, 0)
	game.eliminate(victim, killer, "rifle")
	var death_duration: float = victim.animator.current_animation_length
	assert_almost_eq(victim.respawn_time, death_duration + 1.0, 0.02)
	assert_almost_eq(game.death_view_remaining, death_duration + 1.0, 0.02)
	game._process(0.0)
	assert_eq(game.camera_rig.active_view, "death")
	game.authority = true
	game._physics_process(death_duration)
	game.authority = false
	assert_almost_eq(game.death_view_remaining, 1.0, 0.02)
	game._process(0.0)
	assert_eq(game.camera_rig.active_view, "death")

func test_ocean_death_camera_stops_at_one_metre_and_keeps_looking_at_the_corpse():
	var game:=ArenaMatch.new()
	game.map_id="ramparts";game.online=true;game.authority=false
	add_child_autofree(game)
	await wait_physics_frames(3)
	var victim: ArenaRobot=game.add_robot(0,"SeaCameraProbe",0,true,"projector")
	game.local_robot=victim;game.phase="Active"
	victim.global_position=Vector3(0,-2,0);victim.last_safe=Vector3(0,10,0)
	victim.velocity=Vector3(0,-20,0)
	game.eliminate(victim,null,"Fall off map")
	game._process(0.0)
	assert_almost_eq(game.fall_camera_stop.y,1.0,.0001)
	var stopped: Vector3=game.fall_camera_stop
	game.local_death_corpse.global_position=Vector3(4,-8,3)
	game._process(0.0)
	assert_eq(game.fall_camera_stop,stopped,"The entire follow position stays fixed")
	assert_eq(game.camera_rig.cameras.death.global_position,stopped)
	assert_almost_eq(game.camera_rig.focus_anchors.death.global_position.y,-7.05,.0001)

func test_fall_death_keeps_falling_without_drops_and_camera_stops_at_depth():
	var game := ArenaMatch.new()
	game.online = true
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.authority = false
	var victim: ArenaRobot = game.add_robot(0, "Victim", 0, true, "projector")
	game.local_robot = victim
	game.phase = "Active"
	victim.global_position = Vector3(0, -24, 0)
	victim.last_safe = Vector3(0, 2, 0)
	victim.velocity = Vector3(0, -20, 0)
	victim.ep = 80
	game.eliminate(victim, null, "Fall off map")
	assert_eq(game.corpses.size(), 1)
	assert_eq(game.corpses[0].node.global_position.y, -24.0)
	assert_true(game.corpses[0].falling_out)
	assert_eq(game.corpses[0].ep, 0.0)
	assert_eq(game.corpses[0].node.find_child("RuntimeAnimator", true, false).current_animation, "common_falling")
	assert_false(victim.weapon_pose_visible)
	var fall_skeleton := Assets.find(game.corpses[0].node, "Skeleton3D") as Skeleton3D
	assert_true(game.corpses[0].node.find_children("*", "CollisionObject3D", true, false).is_empty(), "Falling corpses have no live hit bodies")
	assert_eq(fall_skeleton.find_children("*", "MeshInstance3D", true, false).filter(func(node): return String(node.name).begins_with("SK_Pistol")).size(), 0, "Falling death adds no weapon mount")
	assert_almost_eq(victim.respawn_time, 4.0, 0.02)
	game.tick_drops(0.2)
	assert_lt(game.corpses[0].node.global_position.y, -24.0)
	game._process(0.0)
	assert_eq(game.fall_camera_stop.y, -25.0)
	var stopped_at: Vector3 = game.fall_camera_stop
	game.tick_drops(0.2)
	game._process(0.0)
	assert_eq(game.fall_camera_stop, stopped_at)
	assert_almost_eq(game.camera_rig.focus_anchors["death"].global_position.y, game.local_death_corpse.global_position.y + 0.95, 0.001)
	game.tick_drops(5.0)
	assert_eq(game.corpses.size(), 0)
	assert_eq(game.drops.size(), 0)
