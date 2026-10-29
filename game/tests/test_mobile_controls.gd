extends GutTest

const MobileControls = preload("res://scripts/ui/mobile_controls.gd")

func test_touch_icons_rerasterize_at_native_display_density():
	var controls=MobileControls.new()
	add_child_autofree(controls)
	controls.set_process(false)
	for action in controls.icons:
		assert_true(controls.icons[action] is DPITexture,action+" must remain sharp when the content area scales")

func test_multitouch_releases_only_after_last_button_finger():
	var controls = MobileControls.new()
	add_child_autofree(controls)
	controls.set_process(false)
	if not InputMap.has_action("fire"): InputMap.add_action("fire")
	controls.fingers[1] = {"kind":"button", "action":"fire"}
	controls.fingers[2] = {"kind":"button", "action":"fire"}
	controls.set_action("fire", true)
	await get_tree().process_frame
	assert_true(Input.is_action_pressed("fire"))
	controls.release_finger(1)
	await get_tree().process_frame
	assert_true(Input.is_action_pressed("fire"))
	controls.release_finger(2)
	await get_tree().process_frame
	assert_false(Input.is_action_pressed("fire"))

func test_release_all_clears_movement_and_held_action():
	var controls = MobileControls.new()
	add_child_autofree(controls)
	controls.set_process(false)
	if not InputMap.has_action("sprint"): InputMap.add_action("sprint")
	controls.movement = Vector2(0.5, -0.5)
	controls.fingers[1] = {"kind":"move", "origin":Vector2.ZERO}
	controls.fingers[2] = {"kind":"button", "action":"sprint"}
	controls.set_action("sprint", true)
	await get_tree().process_frame
	controls.release_all()
	await get_tree().process_frame
	assert_eq(controls.movement, Vector2.ZERO)
	assert_false(Input.is_action_pressed("sprint"))
	assert_true(controls.fingers.is_empty())

func test_landscape_buttons_do_not_overlap_or_cover_reticle_and_bottom_readouts():
	var controls = MobileControls.new()
	add_child_autofree(controls)
	controls.set_process(false)
	for area in [Vector2(1280,720),Vector2(1600,720),Vector2(960,540)]:
		controls.size=area
		for index in controls.BUTTONS.size():
			var button: Array=controls.BUTTONS[index]
			var center: Vector2=controls.button_center(button)
			var radius: float=controls.button_radius(button[1])*1.15
			assert_true(Rect2(Vector2.ZERO,area).encloses(Rect2(center-Vector2.ONE*radius,Vector2.ONE*radius*2)))
			assert_gt(center.distance_to(area*0.5),radius+area.y*0.08)
			assert_lt(center.y+radius,area.y*0.82)
			for other in range(index+1,controls.BUTTONS.size()):
				var next: Array=controls.BUTTONS[other]
				assert_gt(center.distance_to(controls.button_center(next)),radius+controls.button_radius(next[1])*1.15)


func test_touch_inventory_routes_every_slot_through_shared_input():
	var app_script=load("res://scripts/core/app.gd")
	for slot in 10:
		var event=InputEventAction.new()
		event.action="mobile_slot:%d" % slot
		event.pressed=true
		assert_eq(app_script.numbered_slot(event),slot)


class AimProbe extends RefCounted:
	var yaw := 0.0
	var pitch := 0.0
	func spawn_look_locked(): return false

func test_right_stick_continuously_aims_and_releases_without_moving_robot():
	var controls=MobileControls.new()
	add_child_autofree(controls)
	controls.set_process(false)
	controls.size=Vector2(1280,720)
	var robot=AimProbe.new()
	controls.app={"ui":{"screen":"match","weapon":null},"match_node":{"local_robot":robot},"prefs":{"values":{"sensitivity":0.0022,"invert":false}}}
	var touch=InputEventScreenTouch.new()
	touch.index=7
	touch.pressed=true
	touch.position=controls.aim_center()
	controls._input(touch)
	var drag=InputEventScreenDrag.new()
	drag.index=7
	drag.position=controls.aim_center()+Vector2(72,0)
	controls._input(drag)
	controls._process(0.5)
	var first: float=robot.yaw
	controls._process(0.5)
	assert_almost_eq(first,-1.2,0.001)
	assert_almost_eq(robot.yaw,-2.4,0.001)
	assert_eq(controls.movement,Vector2.ZERO)
	controls.release_all()
	controls._process(0.5)
	assert_eq(controls.aim,Vector2.ZERO)
	assert_almost_eq(robot.yaw,-2.4,0.001)
