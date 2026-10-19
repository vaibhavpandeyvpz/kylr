extends GutTest

class AimWorld extends Node3D:
	var phase := "Active"
	var match_type := "TDM"
	var robots: Array = []
	var local_robot
	var camera: Camera3D
	var rng := RandomNumberGenerator.new()
	var difficulty := 0
	var combat
	var authority := true

class PoseShooter extends ArenaRobot:
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)
	func eye() -> Vector3: return Vector3(0,1.52,0)

func test_pose_aim_preserves_eye_direction_and_local_camera_parallax():
	var world := AimWorld.new()
	add_child_autofree(world)
	var actor := PoseShooter.new()
	actor.arena_match = world
	world.add_child(actor)
	world.robots = [actor]
	world.combat = ArenaCombat.new(world)
	world.camera = Camera3D.new()
	world.add_child(world.camera)
	world.camera.position = Vector3(1,2,0)
	var cover := StaticBody3D.new()
	world.add_child(cover)
	cover.position = Vector3(0,1.52,-3)
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	shape.shape.size = Vector3(5,4,0.2)
	cover.add_child(shape)
	await wait_physics_frames(2)
	for direction in [Vector3.FORWARD,Vector3(0,0.3,-1).normalized()]:
		actor.bot_aim = direction
		var traced: Vector3 = (world.combat.aim_target(actor,15)-actor.eye()).normalized()
		assert_true(actor.pose_aim_direction().is_equal_approx(traced),"Cover on the eye ray does not change remote pose pitch")
	world.local_robot = actor
	actor.human = true
	var camera_traced: Vector3 = (world.combat.aim_target(actor,15)-actor.eye()).normalized()
	assert_true(actor.pose_aim_direction().is_equal_approx(camera_traced),"The local weapon still converges on the camera's cover hit")
	assert_gt(camera_traced.angle_to(actor.aim_direction()),0.01,"The test exercises real camera/eye parallax")

class Shooter extends CharacterBody3D:
	var team := 0
	var protection := 0.0
	var loaded := 50
	var reload_time := 0.0
	var wants_secondary := false
	var equipped := "flamethrower"
	var human := true
	var alive := true
	var hit_rids: Array[RID] = []
	var nozzle := Vector3(0.2, 1.25, -0.5)
	func eye() -> Vector3: return Vector3(0, 1.52, 0)
	func muzzle() -> Vector3: return nozzle
	func aim_direction() -> Vector3: return Vector3.FORWARD
	func can_act() -> bool: return alive and protection <= 0

func test_crosshair_only_contracts_for_damageable_targets_in_range_without_cover():
	var world := AimWorld.new()
	add_child_autofree(world)
	var shooter := Shooter.new()
	world.add_child(shooter)
	shooter.equipped = "pistol"
	world.local_robot = shooter
	world.camera = Camera3D.new()
	world.add_child(world.camera)
	world.camera.position = shooter.eye()
	var victim := ArenaRobot.new()
	autofree(victim)
	victim.arena_match = world
	victim.team = 1
	victim.protection = 0
	world.robots = [shooter, victim]
	var body := StaticBody3D.new()
	world.add_child(body)
	body.position = Vector3(0, 1.52, -6)
	body.collision_layer = 4
	body.set_meta("robot", victim)
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	body.add_child(shape)
	await wait_physics_frames(2)
	var combat := ArenaCombat.new(world)
	assert_true(combat.has_damageable_target(shooter))
	assert_eq(combat.damageable_target(shooter), victim, "The reticle and target name use the same damageable robot")
	victim.sh = 100
	assert_true(combat.has_damageable_target(shooter), "Normal shield still lets AH damage through")
	for state in [{"team": 0}, {"protection": 5.0}, {"alive": false}, {"repair": {"elapsed": 2.0}}]:
		var key: String = state.keys()[0]
		var previous = victim.get(key)
		victim.set(key, state[key])
		assert_false(combat.has_damageable_target(shooter), key)
		victim.set(key, previous)
	body.position.z = -60
	await wait_physics_frames(2)
	assert_false(combat.has_damageable_target(shooter), "Pistol range")
	shooter.equipped = "rifle"
	shooter.wants_secondary = true
	assert_true(combat.has_damageable_target(shooter), "Scoped rifle range")
	var wall := StaticBody3D.new()
	world.add_child(wall)
	wall.position = Vector3(0, 1.5, -2)
	var cover := CollisionShape3D.new()
	cover.shape = BoxShape3D.new()
	cover.shape.size = Vector3(3, 3, 0.2)
	wall.add_child(cover)
	await wait_physics_frames(2)
	assert_false(combat.has_damageable_target(shooter), "Solid cover blocks contraction")

func test_camera_crosshair_convergence_and_muzzle_cover():
	var world := AimWorld.new()
	add_child_autofree(world)
	var robot := Shooter.new()
	world.add_child(robot)
	world.local_robot = robot
	world.robots = [robot]
	world.camera = Camera3D.new()
	world.add_child(world.camera)
	var combat := ArenaCombat.new(world)
	for offset in [Vector3(0, 1.52, 0), Vector3(0.48, 1.77, 2)]:
		world.camera.position = offset
		world.camera.rotation.x = deg_to_rad(-25)
		var target := combat.aim_target(robot, 15)
		assert_gt((target - offset).normalized().dot(-world.camera.global_basis.z), 0.9999)
		assert_gt(combat.shot_direction(robot).dot((target - robot.muzzle()).normalized()), 0.9999)
		var endpoint := combat.flame_endpoint(robot, robot.muzzle())
		assert_almost_eq(endpoint.distance_to(robot.muzzle()), 15.0, 0.001)
		assert_gt((endpoint - robot.muzzle()).normalized().dot(combat.shot_direction(robot)), 0.9999)
	# A short wall hides the muzzle while the shoulder camera can see over it.
	world.camera.position = Vector3(0.48, 1.77, 2)
	world.camera.rotation = Vector3.ZERO
	var wall := StaticBody3D.new()
	world.add_child(wall)
	wall.position = Vector3(0, 0.75, -1)
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	shape.shape.size = Vector3(3, 1.5, 0.1)
	wall.add_child(shape)
	await wait_physics_frames(2)
	assert_lt(combat.flame_endpoint(robot, robot.muzzle()).distance_to(robot.muzzle()), 1.0)
	var direction := combat.shot_direction(robot)
	assert_false(combat.ray(robot.muzzle(), robot.muzzle() + direction * 15, [robot.get_rid()]).is_empty())

func test_flame_visual_stops_at_first_robot_hull_and_nearer_world_cover():
	var world := AimWorld.new()
	add_child_autofree(world)
	var shooter := Shooter.new()
	world.add_child(shooter)
	world.robots = [shooter]
	for distance in [6.0, 9.0]:
		var body := StaticBody3D.new()
		body.collision_layer = 4
		world.add_child(body)
		body.position = Vector3(0.2, 1.25, -distance)
		var shape := CollisionShape3D.new()
		shape.shape = BoxShape3D.new()
		shape.shape.size = Vector3(0.8, 2.0, 0.6)
		body.add_child(shape)
	await wait_physics_frames(2)
	var combat := ArenaCombat.new(world)
	assert_almost_eq(combat.flame_endpoint(shooter, shooter.muzzle()).z, -5.7, 0.01, "Nearest authored robot hull terminates the visible flame")
	var wall := StaticBody3D.new()
	world.add_child(wall)
	wall.position = Vector3(0, 1, -3)
	var cover := CollisionShape3D.new()
	cover.shape = BoxShape3D.new()
	cover.shape.size = Vector3(3, 3, 0.2)
	wall.add_child(cover)
	await wait_physics_frames(2)
	assert_almost_eq(combat.flame_endpoint(shooter, shooter.muzzle()).z, -2.9, 0.01, "Nearer world cover takes precedence")

func test_pistol_fire_keeps_aimed_torso_and_preserves_arm_recoil():
	var character := ContentRegistry.character("tensor")
	var body := Assets.model("characters", character.model)
	add_child_autofree(body)
	var skeleton := Assets.find(body, "Skeleton3D") as Skeleton3D
	var aim := AimPose.new()
	var robot := {"skeleton": skeleton, "character": character, "equipped": "pistol", "anim_state": "", "hit_flash": 0.0}
	var fire := Assets.animation("pistol/fire", character.animation_family)
	var arm := skeleton.find_bone("RightUpperArm")
	assert_gte(arm, 0)
	for time in [0.0, 0.1, 0.2]:
		for angle in [-30, 0, 30]:
			aim.restore(skeleton)
			for track in fire.get_track_count():
				var bone := skeleton.find_bone(String(fire.track_get_path(track)).get_slice(":", 1))
				if bone < 0: continue
				if fire.track_get_type(track) == Animation.TYPE_ROTATION_3D:
					skeleton.set_bone_pose_rotation(bone, fire.rotation_track_interpolate(track, time))
				elif fire.track_get_type(track) == Animation.TYPE_POSITION_3D:
					skeleton.set_bone_pose_position(bone, fire.position_track_interpolate(track, time))
			robot.anim_state = "pistol/idle"
			aim.apply(robot, deg_to_rad(angle))
			var torso: Dictionary = {}
			for name in ["Spine", "Chest", "UpperChest", "Neck", "Head"]:
				var bone := skeleton.find_bone(name)
				torso[bone] = skeleton.get_bone_pose(bone)
			var idle_arm := skeleton.get_bone_pose_rotation(arm)
			aim.restore(skeleton)
			var fired_arm := skeleton.get_bone_pose_rotation(arm)
			var neutral := aim.sample(character.animation_family, "pistol", 0)
			var expected_arm: Quaternion = idle_arm * neutral["RightUpperArm"].rotation.inverse() * fired_arm
			robot.anim_state = "pistol/fire"
			aim.apply(robot, deg_to_rad(angle))
			for bone in torso:
				assert_almost_eq(skeleton.get_bone_pose_rotation(bone).angle_to(torso[bone].basis.get_rotation_quaternion()), 0.0, 0.001, "Firing retains the aimed torso/head pose")
				assert_lt(skeleton.get_bone_pose_position(bone).distance_to(torso[bone].origin), 0.0001)
			assert_almost_eq(skeleton.get_bone_pose_rotation(arm).angle_to(expected_arm), 0.0, 0.001, "Arm firing motion remains additive")
			assert_gt(idle_arm.angle_to(expected_arm), 0.001, "Arm recoil is not flattened into idle")

func test_authored_aim_poses_raise_and_lower_every_weapon_without_accumulation():
	var character := ContentRegistry.character("tensor")
	var body := Assets.model("characters", character.model)
	add_child_autofree(body)
	body.rotation.y = character.forward_yaw
	var skeleton := Assets.find(body, "Skeleton3D") as Skeleton3D
	var aim := AimPose.new()
	for weapon in Arsenal.WEAPONS:
		var idle := aim.sample(character.animation_family, Arsenal.WEAPONS[weapon].animation_family, 0)
		for bone in skeleton.get_bone_count():
			var bone_name := String(skeleton.get_bone_name(bone))
			if idle.has(bone_name) and idle[bone_name].has("rotation"): skeleton.set_bone_pose_rotation(bone, idle[bone_name].rotation)
			if idle.has(bone_name) and idle[bone_name].has("position"): skeleton.set_bone_pose_position(bone, idle[bone_name].position)
		var gun := Assets.model("weapons", weapon)
		add_child(gun)
		var grip := gun.global_transform.affine_inverse() * Assets.socket(gun, "RightHandSocket").global_transform
		var robot := {"skeleton": skeleton, "character": character, "equipped": weapon,"anim_state":"","hit_flash":0.0}
		var hips := skeleton.find_bone("Hips")
		var hip_rotation := skeleton.get_bone_pose_rotation(hips) * Quaternion(Vector3.RIGHT, 0.15)
		skeleton.set_bone_pose_rotation(hips, hip_rotation)
		var leg := skeleton.find_bone("LeftThigh")
		var leg_pose := skeleton.get_bone_pose(leg) if leg >= 0 else Transform3D.IDENTITY
		var elevations: Array[float] = []
		for angle in [-30, 0, 30, 0]:
			aim.restore(skeleton)
			aim.apply(robot, deg_to_rad(angle))
			assert_eq(skeleton.get_bone_pose_rotation(hips), hip_rotation, "Aiming preserves animated hips")
			gun.global_transform = skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone(character.skeleton.weapon_hand)) * grip.affine_inverse()
			var muzzle := Assets.socket(gun, Arsenal.WEAPONS[weapon].muzzles[0])
			var forward := -muzzle.global_basis.z.normalized()
			if angle == 0:
				var left := skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("LeftHand")).origin
				assert_lt(left.distance_to(Assets.socket(gun, "LeftHandSocket").global_position), 0.005, weapon + " support hand stays on grip")
			elevations.append(forward.y)
			assert_almost_eq(rad_to_deg(asin(forward.y)), float(angle), 1.0, weapon + " authored elevation")
			assert_gt(forward.dot(Vector3.FORWARD), 0.5, weapon + " faces forward")
			if leg >= 0: assert_eq(skeleton.get_bone_pose(leg), leg_pose)
		assert_lt(elevations[0], elevations[1] - 0.1, weapon + " aims down")
		assert_gt(elevations[2], elevations[1] + 0.1, weapon + " aims up")
		assert_almost_eq(elevations[1], elevations[3], 0.0001, weapon + " does not accumulate pitch")
		aim.restore(skeleton)
		gun.free()

func test_unchanged_aim_pitch_keeps_live_recoil_and_hip_motion():
	var character := ContentRegistry.character("tensor")
	var body := Assets.model("characters",character.model)
	add_child_autofree(body)
	var skeleton: Skeleton3D = Assets.find(body,"Skeleton3D")
	var aim := AimPose.new()
	var robot := {"skeleton":skeleton,"character":character,"equipped":"pistol","anim_state":"pistol/fire","hit_flash":0.1}
	var hips := skeleton.find_bone("Hips")
	var arm := skeleton.find_bone("RightUpperArm")
	for weapon in Arsenal.WEAPONS:
		robot.equipped = weapon
		robot.anim_state = Arsenal.WEAPONS[weapon].animation_family+"/fire"
		for pitch in [-0.38,-0.36,0.38,0.36,0.38]:
			for motion in [0.1,0.25]:
				aim.restore(skeleton)
				skeleton.set_bone_pose_rotation(hips,Quaternion(Vector3.RIGHT,motion))
				skeleton.set_bone_pose_rotation(arm,Quaternion(Vector3.FORWARD,motion))
				aim.apply(robot,pitch)
				var cached: Array[Transform3D] = []
				for bone in skeleton.get_bone_count(): cached.append(skeleton.get_bone_pose(bone))
				aim.restore(skeleton)
				var fresh := AimPose.new()
				fresh.apply(robot,pitch)
				for bone in cached.size():
					assert_true(cached[bone].is_equal_approx(skeleton.get_bone_pose(bone)),weapon+" keeps live motion at unchanged pitch")
				fresh.restore(skeleton)
