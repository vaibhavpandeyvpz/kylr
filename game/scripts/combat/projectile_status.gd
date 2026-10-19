class_name ProjectileStatus
extends Node

var victim
var attacker
var weapon: String
var remaining := 0.0
var clock := 0.0
var interval := 1.0
var damage := 5.0

func configure(target, source, id: String, profile: Dictionary) -> void:
	victim = target
	attacker = source
	weapon = id
	remaining = float(profile.get("dot_duration",3))
	interval = float(profile.get("dot_interval",1))
	damage = float(profile.get("dot_damage",5))

func _physics_process(dt: float) -> void:
	if not is_instance_valid(victim) or not victim.alive or victim.arena_match.phase != "Active": queue_free(); return
	remaining -= dt
	clock += dt
	while clock >= interval:
		clock -= interval
		victim.hit(damage,attacker if is_instance_valid(attacker) else null,weapon)
	if remaining <= 0: queue_free()
