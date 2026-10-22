class_name PulseProjectileVisual
extends Node3D
## The nose follows flight; the tail leaves the muzzle, then feeds into contact.
const LENGTH_M := 0.25
const RADIUS_M := 0.025
const COLOR := Color(0.0, 0.8, 0.7882353)
static var _material: ShaderMaterial
var length_m := 0.0
var absorbing := false
var absorption_speed := 0.0
var layers: Array[MeshInstance3D] = []

func _ready() -> void:
	if _material == null:
		_material = ShaderMaterial.new()
		_material.shader = preload("res://shaders/original/pulse_packet.gdshader")
	for index in 2:
		var body := MeshInstance3D.new()
		body.name = "PulseCore" if index == 0 else "PulseSheath"
		body.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		body.mesh = EffectMeshes.mesh("PacketShell")
		body.material_override = _material
		body.custom_aabb = AABB(Vector3(-RADIUS_M,-RADIUS_M,0),Vector3(RADIUS_M*2,RADIUS_M*2,LENGTH_M))
		body.set_instance_shader_parameter("core_layer",1.0 if index == 0 else 0.0)
		add_child(body)
		layers.append(body)
	update_length(0)

func update_length(distance: float) -> void:
	length_m = clampf(distance,0,LENGTH_M)
	visible = length_m>0.00001
	for body in layers:
		body.set_instance_shader_parameter("length_m",length_m)

func absorb(point: Vector3, speed: float) -> void:
	reparent(get_parent().get_parent(),true)
	global_position = point
	absorbing = true
	absorption_speed = speed

func _process(dt: float) -> void:
	if not absorbing: return
	update_length(length_m-absorption_speed*dt)
	if length_m<=0: queue_free()
