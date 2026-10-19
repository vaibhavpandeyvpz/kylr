@tool
extends BTAction
@export_enum("egress","emergency","repair","energy","fortify","combat","objective","equipment_urgent","equipment","search","patrol") var intent := "patrol"

func _generate_name() -> String: return "Select " + intent.capitalize()

func _tick(_delta: float) -> Status:
	if not agent.brain.plan_intent(intent): return FAILURE
	blackboard.set_var(&"intent",agent.brain.goal_kind)
	blackboard.set_var(&"destination",agent.brain.goal)
	blackboard.set_var(&"route_nodes",agent.brain.path.size())
	return SUCCESS
