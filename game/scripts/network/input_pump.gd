extends Node
var transport
func _ready(): process_physics_priority = -20
func _physics_process(dt): transport.simulate_inputs(dt)
