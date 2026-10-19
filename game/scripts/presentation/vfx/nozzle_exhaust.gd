class_name NozzleExhaust
extends Node3D

var length_m := 0.38
var radius_m := 0.035
var flame_diameter_m := 0.0
var tint := Color("ff7529")
var emission := 0.65
var plume: OriginalEffect
var particles: Array[GPUParticles3D] = []
var last_fit := Vector2(-1,-1)

func _ready() -> void:
	plume = OriginalEffect.new()
	plume.name = "ExhaustComposition"
	plume.kind = "exhaust"
	plume.emission = emission
	plume.secondary_color = tint
	plume.rotation.x = -PI / 2.0
	add_child(plume)
	_process(0.0)

func _process(_dt: float) -> void:
	var radius := flame_diameter_m * 0.5 if flame_diameter_m > 0.0 else radius_m
	var fit := Vector2(radius,length_m)
	if fit == last_fit: return
	last_fit = fit
	# The entire plume stays inside the native nozzle's radius/length budget.
	plume.update_length(maxf(length_m,0.001),radius * 0.55,radius)

func set_budget(reduced: bool, distance: float) -> void:
	plume.set_budget(reduced,distance)
