class_name ProjectileCollision
extends RefCounted
## Shared convex components from authored collision exports, or visible VFX bodies.
static var cache: Dictionary = {}

static func shapes(weapon: String) -> Array:
	if cache.has(weapon): return cache[weapon]
	var result: Array = []
	if weapon in ["rocket_launcher", "grenade_launcher"]:
		var suffix := "_rocket_col" if weapon == "rocket_launcher" else "_grenade_col"
		var model := Assets.model("weapons", weapon, suffix)
		var skeleton := Assets.find(model, "Skeleton3D") as Skeleton3D
		for mesh in model.find_children("*", "MeshInstance3D", true, false):
			if mesh.skin != null and skeleton != null:
				for hull in CollisionRig.split_hulls(mesh, skeleton):
					var bone := skeleton.find_bone(hull.bone)
					result.append({"shape":hull.shape, "bone":hull.bone, "pose":skeleton.get_bone_global_rest(bone)})
			else:
				result.append({"shape":mesh.mesh.create_convex_shape(), "bone":"", "pose":mesh.transform})
		model.free()
	elif weapon == "emp_gun":
		var box := BoxShape3D.new()
		box.size = Vector3(EmpCharge.INITIAL_RADIUS*2, EmpCharge.INITIAL_RADIUS*2, EmpCharge.LENGTH) * EmpCharge.VISUAL_SCALE
		result.append({"shape":box, "pose":Transform3D.IDENTITY})
	elif weapon == "pulse_gun":
		var cylinder := CylinderShape3D.new()
		cylinder.radius = PulseProjectileVisual.RADIUS_M
		cylinder.height = PulseProjectileVisual.LENGTH_M
		result.append({"shape":cylinder, "pose":Transform3D(Basis(Vector3.RIGHT,PI*0.5),Vector3.ZERO)})
	else:
		var sphere := SphereShape3D.new()
		sphere.radius = FlakRoundVisual.DEFAULT_DIAMETER_M*.5 if weapon == "flak_cannon" else 0.15 if weapon == "bio_rifle" else Arsenal.ORB_DIAMETER*.5
		result.append({"shape":sphere, "pose":Transform3D.IDENTITY})
	for component in result:
		var bounds: AABB = component.shape.get_debug_mesh().get_aabb()
		component.bounds_center = bounds.get_center()
		component.bounds_radius = bounds.size.length() * 0.5 + component.shape.margin
	cache[weapon] = result
	return result

static func local_pose(projectile: Node3D, component: Dictionary) -> Transform3D:
	var pose: Transform3D = component.pose
	if projectile.weapon == "pulse_gun":
		var length := clampf(projectile.travelled,0.001,PulseProjectileVisual.LENGTH_M)
		pose.basis = pose.basis*Basis.from_scale(Vector3(1,length/PulseProjectileVisual.LENGTH_M,1))
		pose.origin.z = length*0.5
		return pose
	if projectile.weapon not in ["rocket_launcher", "grenade_launcher"]: return pose
	var model_basis := Basis(Vector3.UP, PI) if projectile.weapon == "rocket_launcher" else Basis.from_euler(Vector3(projectile.spin,projectile.spin*.6,0))
	var visual: Node3D = projectile.visual
	if is_instance_valid(visual):
		model_basis = visual.basis
		var skeleton := Assets.find(visual, "Skeleton3D") as Skeleton3D
		if skeleton != null and component.get("bone", "") != "":
			var bone := skeleton.find_bone(component.bone)
			if bone >= 0: pose = skeleton.transform * skeleton.get_bone_global_pose(bone)
	# Never inherit the cosmetic first-person launch offset into collision.
	return Transform3D(model_basis, Vector3.ZERO) * pose
