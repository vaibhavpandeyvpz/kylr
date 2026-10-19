extends GutTest

class World extends Node3D:
	var authority := true
	var phase := "Active"
	var robots: Array = []
	var map := {"config":{"model":"faceoff"},"machinery":[]}

class Robot extends ArenaRobot:
	func _ready() -> void:
		set_process(false);set_physics_process(false)
		body_capsule=CapsuleShape3D.new();body_capsule.radius=.32;body_capsule.height=1.72
		body_shape=CollisionShape3D.new();body_shape.shape=body_capsule;body_shape.position.y=.86
		add_child(body_shape)

func test_descending_native_lifts_reverse_before_crushing_a_robot_and_keep_riders():
	for asset in ["bastion","laboratory"]:
		var game := World.new();add_child_autofree(game)
		var suffix: String = "_architecture_"+asset
		var prop := Assets.model("maps","faceoff",suffix);game.add_child(prop)
		CollisionRig.install(prop,"maps","faceoff",null,suffix+"_col")
		var metadata: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/maps/faceoff/faceoff%s_rig.json"%suffix))
		var lift := ArchitectureLift.new()
		lift.install(game,{"node":prop,"asset_suffix":suffix},metadata)
		lift.set_physics_process(false)
		var robot := Robot.new();game.add_child(robot);game.robots.append(robot)
		robot.global_position=lift.surface.global_position
		var floor_y := robot.global_position.y
		lift.motion.play("lift_down",false,"",false,"main",.5)
		lift.traveling=true
		await wait_physics_frames(2)
		var height := lift.surface.global_position.y
		robot.global_position=Vector3(lift.surface.global_position.x,height-.02,lift.surface.global_position.z)
		assert_false(lift.obstructed(Vector3.DOWN*.03),asset+" carries a rider above its deck")
		robot.global_position.y=floor_y
		# Move the deck to just above the standing robot, then run the real controller.
		for frame in 240:
			var before := lift.surface.global_position.y
			lift._physics_process(1.0/60.0)
			await wait_physics_frames(1)
			if lift.motion.channels.main.clip=="lift_up":
				assert_gte(lift.surface.global_position.y,before-.002,asset+" reverses continuously without teleporting down")
				break
		assert_eq(lift.motion.channels.main.clip,"lift_up",asset+" reverses for a robot below")
		assert_almost_eq(robot.global_position.y,floor_y,.001,"Obstruction never pushes the robot below the ground")
		robot.global_position.x+=10
		for frame in 240:
			lift._physics_process(1.0/60.0)
			await wait_physics_frames(1)
		assert_almost_eq(lift.surface.global_position.y,lift.upper,.002,asset+" completes the return upward")
