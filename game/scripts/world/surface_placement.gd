class_name SurfacePlacement
extends RefCounted

static func below(world: World3D, position: Vector3, minimum_y: float) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(position + Vector3.UP * 0.5, position + Vector3.DOWN * 160.0, 1)
	var hit := world.direct_space_state.intersect_ray(query)
	if hit.is_empty() or hit.position.y < minimum_y or hit.collider.get_meta("lethal_surface",false):
		return {}
	return hit

static func ground_mount(root: Node3D, mount: Node3D, point: Vector3) -> void:
	root.global_basis = Basis.IDENTITY
	root.global_position = point
	if mount != null:
		root.global_position += point - mount.global_position
