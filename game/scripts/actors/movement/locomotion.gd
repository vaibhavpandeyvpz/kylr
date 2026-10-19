class_name Locomotion
extends RefCounted

static func footstep_rate(movement_speed: float) -> float:
	return lerpf(1.0, 1.8, clampf((movement_speed - ArenaTuning.WALK_SPEED) / (ArenaTuning.SPRINT_SPEED - ArenaTuning.WALK_SPEED), 0.0, 1.0))

static func horizontal_velocity(current: Vector3, direction: Vector3, target_speed: float, grounded: bool, dt: float) -> Vector3:
	var desired := direction * target_speed
	var rate := ArenaTuning.GROUND_ACCELERATION if grounded else ArenaTuning.AIR_ACCELERATION
	if direction.length_squared() < 0.0001:
		rate = ArenaTuning.GROUND_BRAKING if grounded else ArenaTuning.AIR_BRAKING
	var horizontal := Vector3(current.x, 0.0, current.z).move_toward(desired, rate * dt)
	return Vector3(horizontal.x, current.y, horizontal.z)

static func speed(walk: bool, sprint: bool, energy: float, protected: bool, crouched := false) -> float:
	if crouched: return ArenaTuning.CROUCH_SPEED
	if protected or walk: return ArenaTuning.WALK_SPEED
	if sprint and energy > ArenaTuning.HALF_EP: return ArenaTuning.SPRINT_SPEED
	return ArenaTuning.RUN_SPEED
