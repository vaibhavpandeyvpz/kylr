@tool
extends BTAction

func _generate_name() -> String: return "Observe visible opponents"

func _tick(_delta: float) -> Status:
	if agent.protection > 0:
		agent.brain.target=null
	else:
		agent.brain.perceive()
	blackboard.set_var(&"target_visible",agent.brain.target!=null)
	return SUCCESS
