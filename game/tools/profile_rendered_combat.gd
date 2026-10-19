extends SceneTree

func _initialize() -> void:
	var profile := RenderedCombatProfile.new()
	root.add_child.call_deferred(profile)
