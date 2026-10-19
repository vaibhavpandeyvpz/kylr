extends SceneTree
func _initialize():
	for family in ["pistol","rifle"]:
		for gait in ["walk","run","sprint","crouch_walk"]:
			for direction in ["forward","right","backward","forward_left"]:
				var key: String=family+"/"+gait+"_"+direction
				var animation := Assets.animation(key)
				print("STRIDE ",key," distance=",animation.get_meta("stride_distance",0.0)," duration=",animation.length)
	quit()
