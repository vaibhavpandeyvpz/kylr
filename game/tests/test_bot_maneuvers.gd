extends GutTest

class GroundProbe extends TraversalGraph:
	var gap := false
	func supported(point: Vector3) -> bool:
		return not gap or point.z > -2.0

class SightProbe extends ArenaCombat:
	var ceiling := false
	func clear(from: Vector3, to: Vector3) -> bool:
		return not ceiling or to.y-from.y < 1.0

class RobotProbe extends ArenaRobot:
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)
		character={"eye_height":1.55}

func make_brain() -> ArenaBrain:
	var game := ArenaMatch.new()
	autofree(game)
	game.map=ArenaMap.new()
	autofree(game.map)
	game.map.game=game
	game.map.traversal=GroundProbe.new(game.map)
	game.combat=SightProbe.new(game)
	var robot := RobotProbe.new()
	robot.arena_match=game
	robot.protection=0
	add_child_autofree(robot)
	return ArenaBrain.new(robot)

func test_dodge_jump_rejects_gaps_ceiling_and_unplanned_portals():
	var brain := make_brain()
	var landing := Vector3(0,0,-5)
	assert_true(brain.safe_dodge_jump(landing))
	brain.robot.arena_match.map.traversal.gap=true
	assert_false(brain.safe_dodge_jump(landing))
	brain.robot.arena_match.map.traversal.gap=false
	brain.robot.arena_match.combat.ceiling=true
	assert_false(brain.safe_dodge_jump(landing))
	brain.robot.arena_match.combat.ceiling=false
	brain.robot.arena_match.map.traversal.portal_points.append(Vector3(0,0,-2.5))
	assert_false(brain.safe_dodge_jump(landing))

func test_ep_loss_before_charged_jump_replans_instead_of_holding_forever():
	var brain := make_brain()
	brain.robot.ep=ArenaTuning.HALF_EP
	brain.robot.jump_held=true
	brain.retarget=1
	brain.path=[{"point":Vector3(0,0,-4),"from":Vector3.ZERO,"entry":Vector3.INF,"action":"charged_jump"}]
	brain.steer(1.0/60.0)
	assert_false(brain.robot.jump_held)
	assert_true(brain.path.is_empty())
	assert_eq(brain.transition_index,-1)
	assert_eq(brain.retarget,0.0)

func test_repeatedly_blocked_goal_is_skipped_temporarily():
	var brain := make_brain()
	brain.goal=Vector3(4,0,4)
	brain.goal_kind="ammo"
	for attempt in 3: brain.recover_stuck("walk")
	assert_eq(brain.goal_kind,"reposition")
	assert_gt(brain.blocked_destination_time,0.0)
	assert_false(brain.commit_goal(Vector3(4,0,4),"ammo"))
	assert_true(brain.path.is_empty())

func test_missing_route_reaches_stuck_recovery_instead_of_idling_forever():
	var brain := make_brain()
	brain.goal=Vector3(8,0,8)
	brain.goal_kind="engage"
	brain.retarget=10000
	for frame in 300: brain.steer(1.0/60.0)
	assert_eq(brain.goal_kind,"reposition")
	assert_gt(brain.blocked_destination_time,0.0)
