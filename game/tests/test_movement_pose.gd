extends GutTest

func make_pose() -> MovementPose:
	var body := Assets.model("characters","tensor")
	add_child_autofree(body)
	var pose := MovementPose.new()
	pose.configure(Assets.find(body,"Skeleton3D"),"tensor")
	return pose

func test_stride_phase_tracks_distance_and_stops_when_blocked():
	var pose := make_pose()
	var animation := Assets.animation("rifle/run_forward")
	var stride: float=animation.get_meta("stride_distance",0.0)
	assert_gt(stride,0.1,"Source root translation calibrates the foot cycle")
	for frame in 60: pose.advance(Vector2(0,-stride/60.0),stride/360.0,true,false,false,false,"rifle")
	assert_eq(pose.key,"rifle/run_forward")
	assert_lt(minf(pose.phase,1.0-pose.phase),0.001,"One source stride completes one cycle at actual run speed")
	pose.advance(Vector2(0,-0.1),1.0/60,true,false,false,false,"rifle")
	var phase := pose.phase
	for frame in 20: pose.advance(Vector2.ZERO,1.0/60,true,false,false,false,"rifle")
	assert_eq(pose.key,"rifle/idle")
	assert_eq(pose.phase,phase,"No displacement must not advance a running gait")

func test_lower_body_layer_survives_fire_without_overwriting_arms():
	var pose := make_pose()
	var hand := pose.skeleton.find_bone("RightHand")
	var leg := pose.skeleton.find_bone("LeftUpperLeg")
	var arm_rotation := Quaternion(Vector3.RIGHT,0.3)
	pose.skeleton.set_bone_pose_rotation(hand,arm_rotation)
	pose.advance(Vector2(0,-0.1),1.0/60,true,false,false,false,"rifle")
	pose.apply(0.1)
	var leg_a := pose.skeleton.get_bone_pose_rotation(leg)
	# Simulate a full-body fire clip overwriting the legs every shot.
	pose.skeleton.set_bone_pose_rotation(leg,Quaternion.IDENTITY)
	pose.advance(Vector2(0,-0.1),1.0/60,true,false,false,false,"rifle")
	pose.apply(0.1)
	assert_true(pose.skeleton.get_bone_pose_rotation(hand).is_equal_approx(arm_rotation))
	assert_false(pose.skeleton.get_bone_pose_rotation(leg).is_equal_approx(Quaternion.IDENTITY))
	assert_false(pose.skeleton.get_bone_pose_rotation(leg).is_equal_approx(leg_a),"Legs continue through their stride")

func test_actual_gait_direction_crouch_and_turning():
	var pose := make_pose()
	pose.advance(Vector2(0.1,0),1.0/60,true,false,false,false,"pistol")
	assert_eq(pose.key,"pistol/run_right")
	var phase := pose.phase
	pose.advance(Vector2(-0.1,0),1.0/60,true,false,false,false,"pistol")
	assert_gt(pose.phase,phase,"Direction changes preserve the walking cycle")
	pose.advance(Vector2(-2.5/60,0),1.0/60,true,false,false,true,"pistol")
	assert_eq(pose.key,"pistol/crouch_walk_left")
	pose.advance(Vector2.ZERO,1.0/60,true,false,false,false,"pistol",-0.02)
	assert_eq(pose.key,"pistol/turn_90_right")
	assert_gt(pose.turn_phase,0.0)

func test_run_gait_tolerates_actual_speed_below_requested_limit():
	assert_eq(RobotClips.travel(Vector2.UP,5.99,false,"rifle",0),"run_forward")
	assert_eq(RobotClips.travel(Vector2.UP,11.99,false,"rifle",0),"sprint_forward")

func test_jump_ascent_descent_and_landing_follow_physics():
	var pose := make_pose()
	pose.advance(Vector2.ZERO,1.0/60,false,true,false,false,"pistol",0,5)
	assert_eq(pose.key,"pistol/jump")
	for frame in 20: pose.advance(Vector2.ZERO,1.0/60,false,false,false,false,"pistol",0,2)
	assert_eq(pose.key,"pistol/jump_loop")
	for frame in 20: pose.advance(Vector2.ZERO,1.0/60,false,false,false,false,"pistol",0,-5)
	assert_eq(pose.key,"pistol/jump_loop","An intentional jump retains tucked legs during descent")
	pose.advance(Vector2.ZERO,1.0/60,true,false,false,false,"pistol")
	assert_eq(pose.key,"common/falling_to_landing")
	for frame in 20: pose.advance(Vector2.ZERO,1.0/60,true,false,false,false,"pistol")
	assert_eq(pose.key,"pistol/idle")
	assert_false(pose.airborne_from_jump)
	pose.advance(Vector2.ZERO,1.0/60,false,false,false,false,"pistol",0,-3)
	assert_eq(pose.key,"common/falling","A new ledge fall must not inherit the preceding jump")

func test_charged_jump_preserves_air_loop_across_weapon_change_and_reset():
	var pose := make_pose()
	pose.advance(Vector2.UP*0.1,1.0/60,false,true,true,false,"rifle",0,8)
	for frame in 30: pose.advance(Vector2.UP*0.1,1.0/60,false,false,false,false,"rifle",0,3)
	pose.advance(Vector2.UP*0.1,1.0/60,false,false,false,false,"pistol",0,-8)
	assert_eq(pose.key,"pistol/jump_loop")
	pose.reset()
	assert_false(pose.airborne_from_jump)
	pose.advance(Vector2.ZERO,1.0/60,false,false,false,false,"rifle",0,-3)
	assert_eq(pose.key,"common/falling")

func test_ledge_fall_and_external_launch_do_not_use_ground_gait():
	var pose := make_pose()
	pose.advance(Vector2(0,-0.1),1.0/60,false,false,false,false,"rifle",0,-3)
	assert_eq(pose.key,"common/falling")
	pose.reset()
	pose.advance(Vector2(0,-0.1),1.0/60,false,false,false,false,"rifle",0,10)
	assert_eq(pose.key,"rifle/jump_up","Pad/rocket launch follows upward velocity without a jump button")
	for frame in 40: pose.advance(Vector2(0,-0.1),1.0/60,false,false,false,false,"rifle",0,-3)
	pose.advance(Vector2(0,-0.1),1.0/60,true,false,false,false,"rifle")
	assert_eq(pose.key,"rifle/run_forward","Moving landing keeps the stride under its impact blend")
	assert_eq(pose.landing_clip,"common/falling_to_landing")

func test_aim_preserves_firing_pose_and_hit_layer_restores_without_accumulation():
	var pose := make_pose()
	var character := ContentRegistry.character("tensor")
	var robot := {"skeleton":pose.skeleton,"character":character,"equipped":"rifle","anim_state":"rifle/fire","hit_flash":0.0,"alive":true}
	var aim := AimPose.new()
	var reaction := HitPose.new()
	var hand := pose.skeleton.find_bone("RightHand")
	var arm := pose.skeleton.find_bone("RightUpperArm")
	var fire := Quaternion(Vector3.RIGHT,0.23)
	pose.skeleton.set_bone_pose_rotation(hand,fire)
	aim.apply(robot,0)
	assert_true(pose.skeleton.get_bone_pose_rotation(hand).is_equal_approx(fire),"Level aim must preserve authored firing motion")
	aim.restore(pose.skeleton)
	var before := pose.skeleton.get_bone_pose_rotation(arm)
	robot.hit_flash=0.1
	reaction.apply(robot)
	var hit := pose.skeleton.get_bone_pose_rotation(arm)
	assert_false(hit.is_equal_approx(before),"Taking damage adds an upper-body reaction")
	aim.apply(robot,0)
	assert_true(pose.skeleton.get_bone_pose_rotation(arm).is_equal_approx(hit),"Aim must not erase the hit reaction")
	aim.restore(pose.skeleton)
	reaction.restore(pose.skeleton)
	assert_true(pose.skeleton.get_bone_pose_rotation(arm).is_equal_approx(before))
	reaction.apply(robot)
	assert_true(pose.skeleton.get_bone_pose_rotation(arm).is_equal_approx(hit),"Repeated sampling must not compound the flinch")
