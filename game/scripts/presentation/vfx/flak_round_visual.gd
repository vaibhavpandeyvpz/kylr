class_name FlakRoundVisual
extends Node3D

## Shared visual for physical ballistic rounds. Hitscan shots animate this node
## between muzzle and impact; Flock attaches the same geometry to its real,
## ricocheting projectiles.

const ROUND_SHADER := preload("res://shaders/combat/flak_round.gdshader")
const DEFAULT_DIAMETER_M := 0.05

var diameter_m := DEFAULT_DIAMETER_M
var round_color := Color(1.0, 0.62, 0.22, 1.0)
## Shared ballistic tails are intentionally compact so a fast round reads as a
## projectile rather than a beam.
var tail_length_scale := 0.25
var fragmented := false

static var _shared_material: ShaderMaterial
static var _fragment_material: ShaderMaterial
var _head: MeshInstance3D
var _tail: MeshInstance3D


func _ready() -> void:
	var diameter := clampf(diameter_m, 0.02, 0.12)
	var radius := diameter * 0.5

	var head := MeshInstance3D.new()
	head.name = "TracerHead"
	var head_mesh: Mesh = EffectMeshes.mesh("FragmentChip") if fragmented else ProjectileResources.primitive(&"SphereMesh", {"radius":radius,"height":diameter,"radial_segments":8,"rings":4})
	head.mesh = head_mesh
	_head = head
	if fragmented:
		head.scale = Vector3.ONE*diameter*0.75
		head.custom_aabb = AABB(Vector3.ONE*-0.7,Vector3.ONE*1.4)
		if _fragment_material == null:
			_fragment_material = ShaderMaterial.new()
			_fragment_material.shader = preload("res://shaders/original/flak_fragment.gdshader")
		head.material_override = _fragment_material
		head.set_instance_shader_parameter("round_color",round_color)
		head.set_instance_shader_parameter("emission_energy",2.8)
		head.set_instance_shader_parameter("opacity",1.0)
	else: _configure_material(head, _head_color(), 11.5, 0.0)
	add_child(head)

	var tail := MeshInstance3D.new()
	tail.name = "TracerTail"
	var tail_length := clampf(diameter * 18.0, 0.55, 1.35) * tail_length_scale
	var tail_mesh := ProjectileResources.primitive(&"CylinderMesh", {"top_radius":radius*.12,"bottom_radius":radius*.62,"height":tail_length,"radial_segments":6})
	tail.mesh = tail_mesh
	# CylinderMesh is Y-aligned. The parent projectile's -Z axis points along
	# travel, so +Z is behind the round toward the shooter.
	tail.rotation.x = PI * 0.5
	tail.position.z = tail_length * 0.5
	_tail = tail
	_configure_material(tail, round_color, 6.5, 1.0)
	add_child(tail)


func set_alpha(alpha: float) -> void:
	var clamped_alpha := clampf(alpha, 0.0, 1.0)
	if _head != null:
		_head.set_instance_shader_parameter("opacity", clamped_alpha)
	if _tail != null:
		_tail.set_instance_shader_parameter("opacity", clamped_alpha * 0.9)


func _head_color() -> Color:
	return round_color.lerp(Color(1.0, 0.94, 0.74, 1.0), 0.72)


## Every round shares the shader/material; color, layer and fade belong to the
## mesh instance. Firing must not compile/create two materials per bullet.
static func _configure_material(mesh: MeshInstance3D, color: Color, energy: float, tail_layer: float) -> void:
	prepare_material()
	mesh.material_override = _shared_material
	mesh.set_instance_shader_parameter("round_color", color)
	mesh.set_instance_shader_parameter("emission_energy", energy)
	mesh.set_instance_shader_parameter("tail_layer", tail_layer)
	mesh.set_instance_shader_parameter("opacity", 1.0)


static func prepare_material() -> void:
	if _shared_material == null:
		_shared_material = ShaderMaterial.new()
		_shared_material.shader = ROUND_SHADER
