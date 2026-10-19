class_name BotTeamRoles
extends RefCounted
## Team coordination uses public flag states and friendly positions, never enemy transforms.
var game
var assignments: Dictionary = {}
var signature := ""
var refresh_at := -INF

func _init(controller): game = controller

func role(robot) -> String:
	var key := ""
	for flag in game.flags: key += str(flag.state)+":"+str(flag.carrier)+";"
	for ally in game.robots:
		key += str([ally.robot_id,ally.team,ally.alive,ally.can_act(),ally.carrying])+";"
	if key != signature or game.elapsed >= refresh_at:
		signature = key
		refresh_at = game.elapsed + BotDifficulty.profile(game.difficulty).decision_interval
		reassign()
	return assignments.get(robot.robot_id,"attack")

func choose(pool: Array, point: Vector3, role_name: String, previous: Dictionary):
	if pool.is_empty(): return null
	var selected = null
	var best := INF
	var tactics: Dictionary = BotDifficulty.data.tactics
	for ally in pool:
		var score: float = ally.position.distance_to(point)/float(tactics.objective_weights[role_name])
		# Prefer a healthy, armed escort/recovery robot, without granting extra resources.
		score += (100.0-ally.ah)*0.03 + (3.0 if ally.equipped == "pistol" else 0.0)
		if previous.get(ally.robot_id,"") == role_name: score -= tactics.role_stickiness
		if score < best or (is_equal_approx(score,best) and (selected == null or ally.robot_id < selected.robot_id)):
			best = score
			selected = ally
	pool.erase(selected)
	assignments[selected.robot_id] = role_name
	return selected

func reassign() -> void:
	var previous := assignments.duplicate()
	assignments.clear()
	for team in 2:
		var pool: Array = []
		for ally in game.robots:
			if ally.team != team or not ally.can_act(): continue
			if ally.carrying >= 0: assignments[ally.robot_id] = "extract"
			elif not ally.human: pool.append(ally)
		var own: Dictionary = game.flags[team]
		var enemy: Dictionary = game.flags[1-team]
		if own.state != "home":
			# A dropped flag's point is public. A thief's live point is not.
			choose(pool,own.point if own.state == "dropped" else own.home,"recover",previous)
		if enemy.state == "carried":
			var carrier = game.robot_by_id(enemy.carrier)
			if carrier != null and carrier.team == team: choose(pool,carrier.position,"escort",previous)
		# Leave an attacker available: a lone robot never becomes a permanent defender.
		if own.state == "home" and pool.size() >= 2: choose(pool,own.home,"defend",previous)
		for ally in pool: assignments[ally.robot_id] = "attack"
	if assignments != previous: BotDifficulty.trace("roles",assignments)
