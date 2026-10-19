extends GutTest

class ScheduleWorld extends ArenaMatch:
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)
		map = ArenaMap.new()
		map.game = self
		map.traversal = TraversalGraph.new(map)
	func _exit_tree() -> void:
		if is_instance_valid(map): map.free()

class ScheduleRobot extends ArenaRobot:
	func _ready() -> void:
		set_process(false)
		set_physics_process(false)

class ScheduleBrain extends ArenaBrain:
	func plan_intent(_intent: String) -> bool: return true
	func steer(_dt: float) -> void: pass

func schedule(phases: int) -> Dictionary:
	var previous_phases := ArenaBrain.decision_phases
	ArenaBrain.decision_phases = phases
	var game := ScheduleWorld.new()
	game.match_type = "TDM"
	add_child_autofree(game)
	var actors: Array[ScheduleRobot] = []
	var calls: Array[int] = []
	var last: Array[int] = []
	var intervals: Array[int] = []
	var initial_offsets: Array[float] = []
	var burst := [0]
	var clock := [0]
	for index in 9:
		var actor := ScheduleRobot.new()
		actor.arena_match = game
		actor.robot_id = index+1
		actor.protection = 100.0
		game.add_child(actor)
		game.robots.append(actor)
		actor.brain = ScheduleBrain.new(actor)
		initial_offsets.append(actor.brain.decision)
		actor.brain.reset()
		actors.append(actor)
		calls.append(0)
		last.append(-1)
		actor.brain.behavior.updated.connect(func(_status: int):
			calls[index] += 1
			burst[0] += 1
			if last[index] >= 0: intervals.append(clock[0]-last[index])
			last[index] = clock[0])
	var peak := 0
	for tick in 900:
		clock[0] = tick
		burst[0] = 0
		for actor in actors: actor.brain.tick(1.0/60.0)
		peak = maxi(peak,burst[0])
	ArenaBrain.decision_phases = previous_phases
	return {"calls":calls,"intervals":intervals,"peak":peak,"initial_offsets":initial_offsets}

func test_staggering_preserves_real_tree_update_cadence():
	var original := schedule(1)
	var staggered := schedule(9)
	assert_eq(original.peak,9,"Baseline evaluates the nine native trees together")
	assert_eq(staggered.peak,1,"Offsets spread initial and repeated native updates")
	for index in 9:
		assert_lte(absi(staggered.calls[index]-original.calls[index]),1,"Per-robot count differs only at sample boundaries")
		assert_almost_eq(staggered.initial_offsets[index],float((index+1)%9)*0.25/9.0,0.000001,"Constructor also uses the opt-in phase")
		assert_almost_eq(original.initial_offsets[index],float((index+1)%4)*0.25/4.0,0.000001,"Default constructor keeps legacy offsets")
	assert_eq(staggered.intervals.min(),original.intervals.min())
	assert_eq(staggered.intervals.max(),original.intervals.max())
