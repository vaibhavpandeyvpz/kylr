extends GutTest

class ClosingApp extends Node3D:
	var closing := false

class OrbitRecorder extends RefCounted:
	var calls := 0
	func tick(_dt: float) -> void:
		calls += 1

func test_abort_stops_orbit_callbacks_before_the_match_is_freed():
	var profile: RenderedCombatProfile = autofree(RenderedCombatProfile.new())
	var app: ClosingApp = autofree(ClosingApp.new())
	var match_node: ArenaMatch = autofree(ArenaMatch.new())
	var orbit := OrbitRecorder.new()
	profile.app = app
	profile.game = match_node
	profile.arena_stress = orbit
	app.closing = true
	profile._physics_process(1.0 / 60.0)
	assert_eq(orbit.calls, 0, "An abort must stop camera work before asynchronous application shutdown frees the match.")

func test_freed_match_cannot_receive_an_orbit_callback():
	var profile: RenderedCombatProfile = autofree(RenderedCombatProfile.new())
	var match_node := ArenaMatch.new()
	var orbit := OrbitRecorder.new()
	profile.game = match_node
	profile.arena_stress = orbit
	match_node.free()
	profile._physics_process(1.0 / 60.0)
	assert_eq(orbit.calls, 0, "A retained diagnostic helper must not access a match after its owner frees it.")

func test_shutdown_does_not_update_the_followed_robot():
	var profile: RenderedCombatProfile = autofree(RenderedCombatProfile.new())
	var app: ClosingApp = autofree(ClosingApp.new())
	var match_node: ArenaMatch = autofree(ArenaMatch.new())
	var robot: ArenaRobot = autofree(ArenaRobot.new())
	profile.app = app
	profile.game = match_node
	profile.followed_bot = robot
	robot.pitch = 0.2
	robot.bot_aim = Vector3(0, 0.5, -0.866)
	app.closing = true
	profile._process(1.0 / 60.0)
	assert_almost_eq(robot.pitch, 0.2, 0.00001, "Closing the application must leave followed actors alone during teardown.")
