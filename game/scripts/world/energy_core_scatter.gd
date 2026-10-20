class_name EnergyCoreScatter
extends ProtonScatter
## Runtime placement only; the match owns the independently moving Core nodes.

const SingleItem = preload("res://addons/proton_scatter/src/modifiers/single_item.gd")
const RandomPoints = preload("res://addons/proton_scatter/src/modifiers/create_inside_random.gd")
const ProjectOnColliders = preload("res://addons/proton_scatter/src/modifiers/project_on_geometry.gd")

class PhysicsStepQueries extends ProtonScatterPhysicsHelper:
	var world: World3D
	func execute(queries: Array) -> Array[Dictionary]:
		# Drop placement already runs on the authoritative physics thread.
		# Keep the modifier's batch synchronous with the death/drop transaction.
		var hits: Array[Dictionary] = []
		for query in queries:
			var hit := world.direct_space_state.intersect_ray(query)
			if not hit.is_empty() and hit.collider.get_meta("lethal_surface",false): hit = {}
			hits.append(hit)
		return hits

func _init() -> void:
	enabled = false
	force_rebuild_on_load = false
	var area := ProtonScatterShape.new()
	var sphere := ProtonScatterSphereShape.new()
	sphere.radius = 2.0
	area.shape = sphere
	add_child(area)
	modifier_stack = ProtonScatterModifierStack.new()
	modifier_stack.add(SingleItem.new())
	var random_points := RandomPoints.new()
	random_points.amount = 512
	random_points.restrict_height = true
	modifier_stack.add(random_points)
	var projection := ProjectOnColliders.new()
	projection.ray_offset = 0.5
	projection.ray_length = 0.45
	projection.max_slope = 18.0
	projection.remove_points_on_miss = true
	modifier_stack.add(projection)

func _ready() -> void:
	var queries := PhysicsStepQueries.new()
	queries.world = get_world_3d()
	_physics_helper = queries
	add_child(queries)
	domain = ProtonScatterDomain.new()
	domain.discover_shapes(self)

func positions(origin: Vector3, count: int, random_seed: int) -> Array[Vector3]:
	global_transform = Transform3D(Basis.IDENTITY,origin)
	global_seed = random_seed
	var generated = await modifier_stack.start_update(self,domain)
	var candidates: Array[Vector3] = []
	for placement in generated.list:
		var point: Vector3 = global_transform * placement.origin + Vector3.UP*0.2
		if absf(point.y-origin.y) <= 0.25: candidates.append(point)
	candidates.sort_custom(func(a: Vector3,b: Vector3): return a.distance_squared_to(origin)<b.distance_squared_to(origin))
	var selected: Array[Vector3] = []
	var clearance := PhysicsShapeQueryParameters3D.new()
	var sphere := SphereShape3D.new()
	sphere.radius = 0.125
	clearance.shape = sphere
	clearance.collision_mask = 1
	var space := get_world_3d().direct_space_state
	var progress := true
	while selected.size() < count and progress:
		progress = false
		for candidate in candidates:
			var nearest := INF
			var anchor := origin
			for point in selected:
				var distance := point.distance_to(candidate)
				if distance < nearest: nearest=distance; anchor=point
			if not selected.is_empty() and (nearest < ArenaTuning.DROPPED_CORE_SPACING_MIN or nearest > ArenaTuning.DROPPED_CORE_SPACING_MAX): continue
			if not footprint_supported(candidate): continue
			clearance.transform = Transform3D(Basis.IDENTITY,candidate)
			if not space.intersect_shape(clearance,1).is_empty(): continue
			if not space.intersect_ray(PhysicsRayQueryParameters3D.create(anchor,candidate,1)).is_empty(): continue
			selected.append(candidate)
			progress = true
			if selected.size() == count: break
	# Preserve the EP on a supported point when a cramped ledge cannot fit all Cores.
	while not selected.is_empty() and selected.size() < count: selected.append(selected[0])
	return selected

func footprint_supported(point: Vector3) -> bool:
	for direction in 8:
		var angle := direction * TAU/8.0
		var offset := Vector3(cos(angle),0,sin(angle))*0.125
		var hit := SurfacePlacement.below(get_world_3d(),point+offset,point.y-0.25)
		if hit.is_empty() or hit.normal.y < 0.8 or absf(hit.position.y-(point.y-0.2)) > 0.05: return false
	return true
