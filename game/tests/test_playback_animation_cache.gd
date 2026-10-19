extends GutTest

func root_rotation_tracks(clip: Animation) -> int:
	var count:=0
	for track in clip.get_track_count():
		if clip.track_get_type(track)==Animation.TYPE_ROTATION_3D and String(clip.track_get_path(track)).ends_with(":Root"): count+=1
	return count

func test_shared_playback_variants_preserve_source_and_other_policies():
	var source:=Assets.animation("pistol/run_arc_left")
	assert_not_null(source)
	var source_loop:=source.loop_mode
	var source_tracks:=source.get_track_count()
	assert_gt(root_rotation_tracks(source),0,"Fixture must contain the authored root rotation")
	var stripped:=Assets.playback_animation("pistol/run_arc_left","tensor",false,true)
	assert_same(stripped,Assets.playback_animation("pistol/run_arc_left","tensor",false,true))
	assert_eq(root_rotation_tracks(stripped),0)
	assert_eq(stripped.loop_mode,Animation.LOOP_LINEAR)
	var unstripped:=Assets.playback_animation("pistol/run_arc_left","tensor",true,false)
	assert_ne(unstripped,stripped)
	assert_eq(unstripped.loop_mode,Animation.LOOP_NONE)
	assert_eq(unstripped.get_track_count(),source_tracks)
	assert_eq(source.loop_mode,source_loop)
	assert_eq(source.get_track_count(),source_tracks)
	assert_gt(root_rotation_tracks(source),0,"Shared raw clip remains available to locomotion sampling")

func make_player(body: Node3D,clip: Animation) -> AnimationPlayer:
	var skeleton:=Assets.find(body,"Skeleton3D") as Skeleton3D
	var player:=AnimationPlayer.new()
	player.callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.root_node=NodePath("..")
	skeleton.get_parent().add_child(player)
	var library:=AnimationLibrary.new()
	library.add_animation("shot",clip)
	player.add_animation_library("",library)
	player.play("shot")
	return player

func test_shared_clip_keeps_player_clocks_and_skeleton_poses_independent():
	var a:=Assets.model("characters","tensor")
	var b:=Assets.model("characters","tensor")
	add_child_autofree(a)
	add_child_autofree(b)
	var clip:=Assets.playback_animation("pistol/fire","tensor",true,false)
	var first:=make_player(a,clip)
	var second:=make_player(b,clip)
	first.advance(0.03)
	var skeleton:=Assets.find(a,"Skeleton3D") as Skeleton3D
	var hand:=skeleton.find_bone("RightHand")
	var before:=skeleton.get_bone_pose(hand)
	second.advance(0.16)
	assert_same(first.get_animation("shot"),second.get_animation("shot"))
	assert_almost_eq(first.current_animation_position,0.03,0.00001)
	assert_almost_eq(second.current_animation_position,0.16,0.00001)
	assert_eq(skeleton.get_bone_pose(hand),before,"The other player's advance cannot modify this skeleton")
