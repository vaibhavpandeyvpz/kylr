extends GutTest

func test_marker_and_nameplate_range_ends_at_fifteen_metres():
	assert_true(OpponentMarker.in_camera_range(Vector3.ZERO, Vector3(0, 0, 15)))
	assert_false(OpponentMarker.in_camera_range(Vector3.ZERO, Vector3(0, 0, 15.01)))

func test_team_opponent_marker_respects_mode_life_and_spawn_state():
	var viewer := ArenaRobot.new()
	var target := ArenaRobot.new()
	viewer.team = 0
	target.team = 1
	assert_true(OpponentMarker.eligible("TDM","Active",viewer,target))
	assert_true(OpponentMarker.eligible("CTF","Active",viewer,target))
	assert_false(OpponentMarker.eligible("DM","Active",viewer,target))
	assert_false(OpponentMarker.eligible("TDM","Countdown",viewer,target))
	target.team = 0
	assert_false(OpponentMarker.eligible("TDM","Active",viewer,target))
	target.team = 1
	target.alive = false
	assert_false(OpponentMarker.eligible("CTF","Active",viewer,target))
	target.alive = true
	target.spawn_remaining = 1.0
	assert_false(OpponentMarker.eligible("CTF","Active",viewer,target))
	viewer.free()
	target.free()

func test_opponent_marker_uses_team_color_and_does_not_reveal_through_cover():
	var game := ArenaMatch.new()
	game.online = true
	game.authority = false
	add_child_autofree(game)
	await wait_physics_frames(3)
	game.match_type = "TDM"
	game.phase = "Active"
	var viewer := game.add_robot(0,"Viewer",0,true,"projector") as ArenaRobot
	var target := game.add_robot(1,"Target",1,false,"projector") as ArenaRobot
	game.local_robot = viewer
	viewer.position = Vector3(0,30,0)
	target.position = Vector3(0,30,-6)
	game.camera_rig.freeze_for_capture(Transform3D(Basis.IDENTITY, viewer.eye()))
	await wait_physics_frames(8)
	assert_eq(target.opponent_marker.modulate,game.team_colors[1])
	assert_true(target.opponent_marker.visible,"Visible opponents carry their own team color")
	var wall := StaticBody3D.new()
	wall.collision_layer = 1
	var collision := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(3,3,0.4)
	collision.shape = box
	wall.add_child(collision)
	wall.position = Vector3(0,31,-3)
	add_child_autofree(wall)
	await wait_physics_frames(8)
	assert_false(target.opponent_marker.visible,"Map cover conceals the marker")
	wall.queue_free()
	await wait_physics_frames(8)
	assert_true(target.opponent_marker.visible)
