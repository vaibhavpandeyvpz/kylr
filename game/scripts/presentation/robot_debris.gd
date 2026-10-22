class_name RobotDebris
extends Node3D
## Independent cosmetic assemblies. Physics sees only world geometry (layer 1).
## The authority supplies the initial pose and current body state for late joins;
## clients then simulate locally, without restarting on subsequent snapshots.
const WEAPONS := ["rocket_launcher", "grenade_launcher", "emp_gun"]
const PRESENTATION_SECONDS := 3.0
const BLAST_LAUNCH := {"push_speed":6.0, "scatter_speed":3.0, "lift_speed":2.5, "spin_speed":9.0}
const EMP_LAUNCH := {"push_speed":3.0, "scatter_speed":1.4, "lift_speed":1.0, "spin_speed":5.0}
const FALL_LAUNCH := {"push_speed":2.0, "scatter_speed":2.2, "lift_speed":1.8, "spin_speed":6.0}
const GROUPS := ["Hips", "Chest", "Head", "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot"]
var recipe: Dictionary
var bodies: Dictionary = {}

static func capture(robot: ArenaRobot, cause: String, contact: Dictionary, gravity: float) -> Dictionary:
	var poses: Array[Transform3D] = []
	for bone in robot.skeleton.get_bone_count(): poses.append(robot.skeleton.get_bone_global_pose(bone))
	return {"weapon":cause, "point":contact.get("point", robot.global_position + Vector3.UP),
		"direction":contact.get("direction", Vector3.FORWARD).normalized(), "radial":contact.get("radial", false),
		"velocity":contact.get("velocity", robot.velocity), "seed":randi(), "gravity":gravity,
		"poses":poses, "skeleton":robot.body.global_transform.affine_inverse() * robot.skeleton.global_transform}

static func group_for(skeleton: Skeleton3D, bone: int) -> String:
	while bone >= 0:
		var id := String(skeleton.get_bone_name(bone))
		if id in GROUPS: return id
		bone = skeleton.get_bone_parent(bone)
	return "Hips"

func build(robot: ArenaRobot, data: Dictionary, materials: Dictionary, render_meshes := true) -> void:
	recipe = data
	var skeleton := robot.skeleton
	var poses: Array = recipe.poses
	var frame: Transform3D = global_transform * recipe.skeleton
	var material := PhysicsMaterial.new()
	material.friction = 0.85
	material.bounce = 0.15
	# Reuse the active head/body's installed convex hulls, including compound shapes.
	for attachment: BoneAttachment3D in skeleton.find_children("*", "BoneAttachment3D", true, false):
		for collider in attachment.get_children():
			if not collider is CollisionObject3D or not collider.has_meta("robot"): continue
			var group := group_for(skeleton, skeleton.find_bone(attachment.bone_name))
			var body := _body_for(group, skeleton, poses, frame, material)
			var shape_frame: Transform3D = body.global_transform.affine_inverse() * frame * poses[skeleton.find_bone(attachment.bone_name)]
			for original in collider.get_children():
				if not original is CollisionShape3D: continue
				var shape := CollisionShape3D.new()
				shape.shape = original.shape
				body.add_child(shape)
				shape.transform = shape_frame * collider.transform * original.transform
	if render_meshes:
		for source: MeshInstance3D in robot.body.find_children("*", "MeshInstance3D", true, false):
			if not source.visible or source.skin == null or String(source.name).begins_with("SK_TensorShield"): continue
			var finishes: Array[Material] = []
			for surface in source.mesh.get_surface_count():
				finishes.append(Assets.extinguished_material(source.get_active_material(surface), materials))
			for fragment in RobotDebrisMesh.fragments(source, skeleton):
				var bone := skeleton.find_bone(fragment.bone)
				var group := group_for(skeleton, bone)
				var body := _body_for(group, skeleton, poses, frame, material)
				var visual := MeshInstance3D.new()
				visual.mesh = fragment.mesh
				visual.material_override = finishes[fragment.surface]
				visual.cast_shadow = source.cast_shadow
				body.add_child(visual)
				visual.global_transform = frame * poses[bone]
	var random := RandomNumberGenerator.new()
	random.seed = recipe.seed
	var launch: Dictionary = EMP_LAUNCH if recipe.weapon == "emp_gun" else BLAST_LAUNCH
	if recipe.weapon == "Fall off map": launch = FALL_LAUNCH
	var center := global_position + Vector3.UP * 0.95
	for body: RigidBody3D in bodies.values():
		var outward := (body.global_position - center).normalized()
		var push: Vector3 = (body.global_position - recipe.point).normalized() if recipe.radial else recipe.direction
		if push.is_zero_approx(): push = recipe.direction
		var scatter := outward * float(launch.scatter_speed) + Vector3(random.randf_range(-0.5,0.5), random.randf_range(0.0,0.6), random.randf_range(-0.5,0.5))
		body.linear_velocity = recipe.velocity + push * float(launch.push_speed) + scatter + Vector3.UP * float(launch.lift_speed)
		body.angular_velocity = Vector3(random.randf_range(-1,1), random.randf_range(-1,1), random.randf_range(-1,1)) * float(launch.spin_speed)

func _body_for(group: String, skeleton: Skeleton3D, poses: Array, frame: Transform3D, material: PhysicsMaterial) -> RigidBody3D:
	if bodies.has(group): return bodies[group]
	var body := RigidBody3D.new()
	body.name = group
	body.collision_layer = 0
	body.collision_mask = 1
	body.gravity_scale = float(recipe.gravity) / float(ProjectSettings.get_setting("physics/3d/default_gravity", 9.8))
	body.continuous_cd = true
	body.linear_damp = 0.15
	body.angular_damp = 0.8
	body.physics_material_override = material
	add_child(body)
	body.global_transform = frame * poses[skeleton.find_bone(group)]
	bodies[group] = body
	return body

func focus_position() -> Vector3:
	return (bodies["Chest"] as RigidBody3D).global_position if bodies.has("Chest") else global_position + Vector3.UP * 0.95

func snapshot() -> Dictionary:
	var state: Dictionary = {}
	for id: String in bodies:
		var body: RigidBody3D = bodies[id]
		state[id] = {"transform":body.global_transform, "linear":body.linear_velocity, "angular":body.angular_velocity, "sleeping":body.sleeping}
	return {"recipe":recipe, "bodies":state}

func restore(state: Dictionary) -> void:
	for id: String in state:
		if not bodies.has(id): continue
		var body: RigidBody3D = bodies[id]
		body.global_transform = state[id].transform
		body.linear_velocity = state[id].linear
		body.angular_velocity = state[id].angular
		body.sleeping = state[id].sleeping
