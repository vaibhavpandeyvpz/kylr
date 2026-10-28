class_name LavaDeath
extends RefCounted
## Animated sinking with a stationary, obstruction-tested spectator position.

const SINK_DEPTH := 2.4

static func begin(world: ArenaMatch, corpse: Node3D, height: float, duration: float, seed_value: int) -> void:
	var origin := corpse.global_position
	origin.y = height
	corpse.global_position = origin
	corpse.set_meta("lava_origin", origin)
	var recipe := {"start":world.elapsed,"duration":duration,"seed":seed_value}
	corpse.set_meta("lava_bubbles",recipe)
	LavaDeathBubbles.attach(world,corpse,recipe)

static func camera_position(game: ArenaMatch, corpse: Node3D, yaw: float) -> Vector3:
	if corpse.has_meta("lava_camera"): return corpse.get_meta("lava_camera")
	var origin: Vector3 = corpse.get_meta("lava_origin")
	var focus := origin + Vector3.UP * 0.9
	var best := focus + Vector3.UP * 6.0
	var best_score := -INF
	var clearance := SphereShape3D.new()
	clearance.radius = 0.22
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = clearance
	query.collision_mask = 1
	# Prefer a front three-quarter view, then try both banks and higher angles.
	# This bounded search runs once per local death, never every render frame.
	for elevation in [2.5, 4.0, 6.0]:
		for index in 12:
			var angle := yaw + PI * 0.85 + TAU * index / 12.0
			var point := origin + Vector3(sin(angle) * 4.5, elevation, cos(angle) * 4.5)
			var hit := game.combat.ray(focus, point, [], 1)
			if not hit.is_empty(): continue
			# Keep the lower silhouette clear too, and leave room for the lens.
			if not game.combat.ray(origin + Vector3.UP * 0.15, point, [], 1).is_empty(): continue
			query.transform.origin = point
			if not game.get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty(): continue
			var score: float = -float(index) * 0.05 - elevation
			if score > best_score:
				best = point
				best_score = score
	corpse.set_meta("lava_camera", best)
	return best
