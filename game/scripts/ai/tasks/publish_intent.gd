@tool
extends BTAction

func _generate_name() -> String: return "Publish tactical state"

func _tick(_delta: float) -> Status:
	blackboard.set_var(&"intent",agent.brain.goal_kind)
	blackboard.set_var(&"destination",agent.brain.goal)
	blackboard.set_var(&"route_nodes",agent.brain.path.size())
	BotDifficulty.trace("decision",{"robot":agent.get("robot_id"),"goal":agent.brain.goal_kind,"visible":agent.brain.target!=null,"route_nodes":agent.brain.path.size()})
	return SUCCESS
