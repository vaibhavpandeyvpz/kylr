class_name OpponentMarker
extends Label3D

var robot: ArenaRobot
var arena_match: ArenaMatch
var visibility_elapsed := 0.0
const MAX_CAMERA_DISTANCE := 15.0

func _ready() -> void:
	text = "◆"
	position.y = 2.16
	billboard = BaseMaterial3D.BILLBOARD_ENABLED
	fixed_size = true
	pixel_size = 0.002
	font_size = 24
	outline_size = 5
	outline_modulate = Color(0, 0, 0, 0.9)
	no_depth_test = false
	visibility_range_end = MAX_CAMERA_DISTANCE
	visible = false

static func in_camera_range(camera_position: Vector3, target_position: Vector3) -> bool:
	return camera_position.distance_squared_to(target_position) <= MAX_CAMERA_DISTANCE * MAX_CAMERA_DISTANCE

static func eligible(mode: String, phase: String, viewer: ArenaRobot, target: ArenaRobot) -> bool:
	return (mode == "TDM" or mode == "CTF") and phase == "Active" and viewer != null and target != null \
		and viewer != target and viewer.team != target.team and viewer.alive and target.alive \
		and target.spawn_remaining <= 0.0

func _physics_process(dt: float) -> void:
	visibility_elapsed -= dt
	if visibility_elapsed > 0.0: return
	visibility_elapsed = 0.1
	if arena_match == null or not eligible(arena_match.match_type, arena_match.phase, arena_match.local_robot, robot) or not robot.is_visible_in_tree() \
		or arena_match.camera == null or not in_camera_range(arena_match.camera.global_position, robot.global_position):
		visible = false
		return
	var viewer := arena_match.local_robot as ArenaRobot
	var query := PhysicsRayQueryParameters3D.create(viewer.eye(), robot.eye())
	query.collision_mask = 1
	visible = viewer.get_world_3d().direct_space_state.intersect_ray(query).is_empty()
