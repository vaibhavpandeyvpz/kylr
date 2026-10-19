extends GutTest

class GoalTraversal extends TraversalGraph:
	var calls := 0
	func route(a: Vector3,b: Vector3,_charged := true,_grounded := false) -> Array:
		calls += 1
		return [{"from":a,"point":b,"action":"walk"}]

class GoalMap extends ArenaMap:
	func can_collect(_fixture: Dictionary,_robot) -> bool: return true

class GoalWorld extends ArenaMatch:
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)
		phase = "Active"
		map = GoalMap.new()
		map.game = self
		map.traversal = GoalTraversal.new(map)
	func _exit_tree() -> void:
		if is_instance_valid(map): map.free()

class GoalRobot extends ArenaRobot:
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)

func fixture() -> GoalRobot:
	var game := GoalWorld.new()
	add_child_autofree(game)
	var actor := GoalRobot.new()
	actor.arena_match = game
	game.add_child(actor)
	game.robots.append(actor)
	actor.brain = ArenaBrain.new(actor)
	actor.brain.goal_kind = "engage"
	actor.brain.goal = Vector3(0,0,-10)
	actor.brain.path = [{"from":Vector3.ZERO,"point":actor.brain.goal,"action":"walk"}]
	actor.brain.seen = Vector3(8,0,-15)
	actor.brain.memory = float(actor.brain.tuning.memory_seconds) - 0.1
	actor.protection = 0.0
	actor.spawn_remaining = 0.0
	return actor

func test_brief_occlusion_preserves_unfinished_route_without_a_hidden_target():
	var actor := fixture()
	var destination: Vector3 = actor.brain.goal
	assert_true(actor.brain.plan_intent("search"))
	assert_eq(actor.brain.goal_kind,"engage")
	assert_eq(actor.brain.goal,destination)
	assert_eq(actor.arena_match.map.traversal.calls,0,"Do not rebuild a route just because sight flickers")
	assert_null(actor.brain.target,"Movement continuity must not reacquire an unseen target")

func test_sustained_occlusion_searches_only_the_remembered_point():
	var actor := fixture()
	actor.brain.memory = float(actor.brain.tuning.memory_seconds) - 0.6
	assert_true(actor.brain.plan_intent("search"))
	assert_eq(actor.brain.goal_kind,"search")
	assert_eq(actor.brain.goal,actor.brain.seen)
	assert_eq(actor.arena_match.map.traversal.calls,1)

func test_completion_missing_route_and_damage_bypass_the_grace():
	for reason in ["completed","missing_route","damage"]:
		var actor := fixture()
		if reason == "completed": actor.position = actor.brain.goal
		if reason == "missing_route": actor.brain.path.clear()
		if reason == "damage": actor.hit_flash = 0.2
		assert_true(actor.brain.plan_intent("search"),reason)
		assert_eq(actor.brain.goal_kind,"search",reason)
		assert_eq(actor.brain.goal,actor.brain.seen,reason)

func test_repair_priority_can_interrupt_the_retained_combat_route():
	var actor := fixture()
	actor.ah = 40.0
	var station := Vector3(2,0,-5)
	actor.arena_match.map.fixtures = [{"kind":"repair_station","point":station,"cooldown":0.0,"occupant":null,"id":"repair"}]
	assert_true(actor.brain.plan_intent("repair"))
	assert_eq(actor.brain.goal_kind,"repair")
	assert_eq(actor.brain.goal,station)

func test_low_energy_priority_can_interrupt_the_retained_combat_route():
	var actor := fixture()
	actor.ep = 40.0
	var core := Vector3(-2,0,-5)
	actor.arena_match.map.fixtures = [{"kind":"energy","point":core,"id":"energy"}]
	assert_true(actor.brain.plan_intent("energy"))
	assert_eq(actor.brain.goal_kind,"energy")
	assert_eq(actor.brain.goal,core)
