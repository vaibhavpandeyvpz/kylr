class_name FireOrb
extends Node3D

var composition: OriginalEffect

func _ready() -> void:
	composition = OriginalEffect.new()
	composition.name = "ThermalComposition"
	composition.kind = "orb"
	composition.emission = 0.8
	composition.scale = Vector3.ONE * Arsenal.ORB_DIAMETER
	add_child(composition)
