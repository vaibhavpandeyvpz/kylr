class_name ImpactShake
extends RefCounted
## Shaker supplies the pattern; this envelope bounds local cosmetic feedback.
var preset := ShakerPreset3D.new()
var strength := 0.0
var remaining := 0.0
var duration := 0.4
var clock := 0.0

func _init() -> void:
	var texture := NoiseTexture3D.new()
	texture.width=16;texture.height=16;texture.depth=16
	var noise := FastNoiseLite.new()
	noise.seed=1207
	noise.frequency=1.2
	texture.noise=noise
	var position_noise := ShakerTypeNoiseShake3D.new()
	position_noise.noise_texture=texture
	position_noise.amplitude=Vector3(0.018,0.022,0.008)
	var rotation_noise := ShakerTypeNoiseShake3D.new()
	rotation_noise.noise_texture=texture
	rotation_noise.amplitude=Vector3(0.007,0.009,0.012)
	preset.PositionShake=[position_noise]
	preset.RotationShake=[rotation_noise]

static func blast_strength(center: Vector3, target: Vector3, radius: float) -> float:
	if not center.is_finite() or not target.is_finite() or not is_finite(radius) or radius<=0: return 0.0
	return clampf(1.0-center.distance_to(target)/radius,0.0,1.0)

func trigger(cause: String, intensity: float) -> void:
	if cause not in ["rocket_launcher","grenade_launcher","emp_gun","Fall off map"] or not is_finite(intensity) or intensity<=0: return
	var incoming := minf(intensity,1.0)
	var residual := strength*pow(clampf(remaining/duration,0,1),2)
	strength=minf(1.0,maxf(residual,incoming)+minf(residual,incoming)*0.15)
	duration=maxf(remaining,0.24 if cause=="emp_gun" else 0.42)
	remaining=duration

func clear() -> void:
	strength=0
	remaining=0

func sample(dt: float) -> Transform3D:
	clock+=dt
	remaining=maxf(0,remaining-dt)
	if remaining<=0:
		clear()
		return Transform3D.IDENTITY
	var envelope := strength*pow(clampf(remaining/duration,0,1),2)
	var offset := (preset.get_value(clock,ShakerPreset3D.Categories.POSITION)*envelope).limit_length(0.04)
	var rotation := (preset.get_value(clock,ShakerPreset3D.Categories.ROTATION)*envelope).clamp(Vector3.ONE*-0.02,Vector3.ONE*0.02)
	return Transform3D(Basis.from_euler(rotation),offset)
