class_name Knockback
extends RefCounted

# Speeds in metres/second. Gravity and collision remain the actor's normal physics.
static func impulse(direction: Vector3, speed: float, bounce: float, strength := 1.0) -> Vector3:
	var horizontal := Vector3(direction.x, 0, direction.z).normalized()
	return (horizontal * speed + Vector3.UP * bounce) * clampf(strength, 0, 1)

static func rocket(direction: Vector3, distance := 0.0) -> Vector3:
	var strength := clampf(1.0 - distance / ArenaTuning.ROCKET_SPLASH_RADIUS, 0.0, 1.0)
	# Even the outermost damaging splash gives a small kick.
	if distance <= ArenaTuning.ROCKET_SPLASH_RADIUS: strength = maxf(0.15, strength)
	return impulse(direction, ArenaTuning.ROCKET_PUSH_SPEED, ArenaTuning.ROCKET_BOUNCE_SPEED, strength)

static func emp(direction: Vector3) -> Vector3:
	return impulse(direction, ArenaTuning.EMP_PUSH_SPEED, ArenaTuning.EMP_BOUNCE_SPEED)

static func grenade(direction: Vector3, distance := 0.0, radius := 5.0) -> Vector3:
	if distance>=radius: return Vector3.ZERO
	return impulse(direction,ArenaTuning.GRENADE_PUSH_SPEED,ArenaTuning.GRENADE_BOUNCE_SPEED,maxf(.15,1.0-distance/radius))
