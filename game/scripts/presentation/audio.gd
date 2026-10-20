class_name ArenaAudio
extends SpatialAudioDirector

var energy_pickups: Array[Dictionary] = []
var energy_pickup_wait := 0.0

func energy_core_pickup(point: Vector3, local: bool, emitter: ArenaRobot) -> void:
	if game is ArenaMatch and game.replicating and game.authority:
		game.present({"kind":"audio","cue":"pickup_item","point":point,"near":local,"emitter":emitter.robot_id,"individual":true})
		return
	if not local and listener_position().distance_to(point) >= float(AudioCues.profile("pickup_item").far): return
	energy_pickups.append({"point":point,"local":local})

func _physics_process(dt):
	super(dt)
	energy_pickup_wait = maxf(0,energy_pickup_wait-dt)
	if energy_pickups.is_empty() or energy_pickup_wait > 0: return
	# Separate a cluster's arrivals so every Core gets an audible pickup transient.
	var pickup: Dictionary = energy_pickups.pop_front()
	play_cue("pickup_item",pickup.point,pickup.local,AudioCues.profile("pickup_item"))
	energy_pickup_wait = 0.08
