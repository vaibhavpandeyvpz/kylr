extends GutTest

class IntentProbe extends RefCounted:
	var accepted: Array = []
	var target = null
	var goal_kind := ""
	var goal := Vector3.ZERO
	var path: Array = []
	var observations := 0
	func perceive(): observations += 1
	func plan_intent(intent: String) -> bool:
		if intent not in accepted: return false
		goal_kind=intent
		return true

class ProbeAgent extends Node3D:
	var protection := 0.0
	var brain := IntentProbe.new()

func test_mode_trees_preempt_combat_for_survival_and_react_to_recovery():
	for mode in ["dm","tdm","ctf"]:
		var robot := ProbeAgent.new()
		add_child_autofree(robot)
		var player := BTPlayer.new()
		player.update_mode=BTPlayer.MANUAL
		player.behavior_tree=load("res://data/ai/trees/"+mode+".tres")
		player.set_scene_root_hint(robot)
		robot.add_child(player)
		robot.brain.accepted=["repair","combat","patrol"]
		player.update(0.25)
		assert_eq(player.blackboard.get_var("intent"),"repair",mode)
		robot.brain.accepted=["combat","patrol"]
		player.update(0.25)
		assert_eq(player.blackboard.get_var("intent"),"combat",mode)
		robot.protection=5
		robot.brain.accepted=["egress","combat"]
		player.update(0.25)
		assert_eq(player.blackboard.get_var("intent"),"egress",mode)
		assert_eq(robot.brain.observations,2,"Protection must suppress target acquisition")
