class_name Spatio
extends RefCounted

# A small, deterministic acoustic model over the same collision geometry used by
# gameplay. One sample costs exactly three physics rays; no scene meshes are
# copied and no unbounded reflection jobs are created during combat.
const RAYS_PER_SAMPLE := 3
const RAYS_PER_TICK := 15
const EAR_SPREAD := 0.22
const EMITTER_CLEARANCE := 0.25
const MATERIALS := {
	"concrete": Vector2(0.48, 0.16),
	"metal": Vector2(0.55, 0.19),
	"glass": Vector2(0.76, 0.43),
	"grate": Vector2(0.83, 0.60),
	"fabric": Vector2(0.92, 0.54),
	"open": Vector2.ONE,
}

static func material_for_name(name: String, category := "") -> String:
	var label := name.to_lower()
	if "glass" in label: return "glass"
	if "grate" in label or "grid" in label or "fence" in label: return "grate"
	if "cloth" in label or "fabric" in label: return "fabric"
	if "rock" in label or "regolith" in label or "concrete" in label: return "concrete"
	if "metal" in label or "steel" in label or "barricade" in label or "door" in label: return "metal"
	return "concrete" if category == "maps" else "metal"

static func transmission(collider: Object) -> Vector2:
	if collider is Node and collider.has_meta("spatio_material"):
		return MATERIALS.get(String(collider.get_meta("spatio_material")).to_lower(), MATERIALS.concrete)
	return MATERIALS.concrete

static func sample(space: PhysicsDirectSpaceState3D, ear: Vector3, source: Vector3) -> Dictionary:
	var path := source - ear
	if path.length_squared() < 0.25:
		return {"low":1.0, "high":1.0, "blocked":0.0, "rays":0}
	var direction := path.normalized()
	var side := direction.cross(Vector3.UP).normalized()
	if side.length_squared() < 0.01: side = direction.cross(Vector3.FORWARD).normalized()
	var endpoint := source - direction * EMITTER_CLEARANCE + Vector3.UP * 0.08
	var low := 0.0
	var high := 0.0
	var blocked := 0.0
	# Keep every ray live; reuse only its parameters within this synchronous sample.
	var query := PhysicsRayQueryParameters3D.create(ear, endpoint, 1)
	for offset in [-EAR_SPREAD, 0.0, EAR_SPREAD]:
		query.from = ear + side * offset
		query.to = endpoint + side * offset
		var hit := space.intersect_ray(query)
		if hit.is_empty():
			low += 1.0
			high += 1.0
		else:
			var passband := transmission(hit.collider)
			low += passband.x
			high += passband.y
			blocked += 1.0
	return {"low":low / RAYS_PER_SAMPLE, "high":high / RAYS_PER_SAMPLE,
		"blocked":blocked / RAYS_PER_SAMPLE, "rays":RAYS_PER_SAMPLE}
