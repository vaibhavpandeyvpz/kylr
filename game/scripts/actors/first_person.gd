class_name FirstPersonRig
extends Node3D

var robot
var camera: Camera3D
var gun: Node3D
var weapon_id := ""
const SCREEN_REGION := Rect2(0.42, 0.60, 0.31, 0.52)
const WEAPON_REGIONS := {}
const VIEW_DEPTH := 0.8
const CAMERA_OFFSET := Vector3(0.0, -0.05, 0.10)
const SCREEN_ANCHOR_X := 0.575
var weapon_bounds: AABB
var framing := Transform3D.IDENTITY
var viewport_size := Vector2.ZERO
var view_fov := 0.0

func _ready():
 process_priority = 320
 hide()

func _process(_dt):
 visible = robot.arena_match.uses_first_person()
 if not visible: return
 if weapon_id != robot.equipped:
  if gun: gun.free()
  weapon_id = robot.equipped
  gun = Assets.model("weapons",Arsenal.WEAPONS[weapon_id].model)
  add_child(gun)
  disable_mesh_shadows(gun)
  var pack := Assets.socket(gun,"AmmoMount")
  if pack:
   var ammo := Assets.model("weapons",weapon_id,"_ammo")
   pack.add_child(ammo)
   disable_mesh_shadows(ammo)
  weapon_bounds = mesh_bounds(gun)
  viewport_size = Vector2.ZERO
 gun.show()
 var source_skeleton := Assets.find(robot.gun,"Skeleton3D") as Skeleton3D
 var target_skeleton := Assets.find(gun,"Skeleton3D") as Skeleton3D
 for bone in target_skeleton.get_bone_count():
  var source_id := source_skeleton.find_bone(target_skeleton.get_bone_name(bone))
  if source_id >= 0: target_skeleton.set_bone_pose(bone,source_skeleton.get_bone_pose(source_id))
 target_skeleton.force_update_all_bone_transforms()
 if viewport_size != camera.get_viewport().get_visible_rect().size or view_fov != camera.fov:
  frame_weapon()
 var target: Vector3 = robot.arena_match.combat.aim_target(robot, Arsenal.WEAPONS[weapon_id].range)
 gun.global_transform = camera.global_transform * aimed_framing(camera.global_transform.affine_inverse() * target)
 if weapon_id in ["rifle", "rocket_launcher"] and robot.wants_secondary:
  gun.hide()

func mesh_bounds(root: Node3D) -> AABB:
 var bounds := AABB()
 var first := true
 for mesh: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
  var local: AABB = (root.global_transform.affine_inverse() * mesh.global_transform) * mesh.get_aabb()
  bounds = local if first else bounds.merge(local)
  first = false
 return bounds

func frame_weapon() -> void:
 viewport_size = camera.get_viewport().get_visible_rect().size
 view_fov = camera.fov
 # Imported barrels face +Z. View along the barrel from behind the receiver.
 var outward_yaw := 0.35 * minf(1.0, viewport_size.aspect())
 var orientation := Basis(Vector3.UP, PI - outward_yaw)
 var center := weapon_bounds.get_center()
 var camera_inverse := camera.global_transform.affine_inverse()
 var region := screen_region()
 var top_left := camera_inverse * camera.project_position(region.position * viewport_size, VIEW_DEPTH) / VIEW_DEPTH
 var bottom_right := camera_inverse * camera.project_position(region.end * viewport_size, VIEW_DEPTH) / VIEW_DEPTH
 var points: Array[Vector3] = []
 var nearest := 0.0
 for corner in 8:
  var point := orientation * (weapon_bounds.get_endpoint(corner) - center)
  points.append(point)
  nearest = maxf(nearest, point.z)
 var small := 0.0
 var large := (VIEW_DEPTH - camera.near * 1.1) / maxf(nearest, 0.01)
 var anchor := camera_inverse * camera.project_position(Vector2(SCREEN_ANCHOR_X, 0.5) * viewport_size, VIEW_DEPTH)
 # Fit around the fixed horizontal anchor; crop only below the screen.
 for iteration in 32:
  var candidate := (small + large) * 0.5
  var limits := framing_limits(points, candidate, top_left, bottom_right)
  if limits.x <= anchor.x and anchor.x <= limits.y and limits.z <= limits.w: small = candidate
  else: large = candidate
 var limits := framing_limits(points, small, top_left, bottom_right)
 var offset := Vector3((limits.x + limits.y) * 0.5, limits.z, -VIEW_DEPTH)
 offset.x = anchor.x
 framing = Transform3D(orientation.scaled(Vector3.ONE * small), offset - orientation * center * small)
 framing.origin += CAMERA_OFFSET

func screen_region() -> Rect2:
 return WEAPON_REGIONS.get(weapon_id, SCREEN_REGION)

func aimed_framing(target: Vector3) -> Transform3D:
 var muzzles: Array = Arsenal.WEAPONS[weapon_id].muzzles
 var muzzle := Assets.socket(gun, "Muzzle1" if weapon_id == "rocket_launcher" else muzzles[robot.barrel % muzzles.size()])
 var socket_frame := gun.global_transform.affine_inverse() * muzzle.global_transform
 var center := weapon_bounds.get_center()
 var pivot := framing * center
 var aligned := framing
 # Rotate about the existing weapon center; animated barrel sockets define the aim axis.
 for iteration in 8:
  var muzzle_position := aligned * socket_frame.origin
  var forward := (aligned.basis * -socket_frame.basis.z).normalized()
  var desired := (target - muzzle_position).normalized()
  var correction := Basis(Quaternion(forward, desired))
  aligned.basis = correction * aligned.basis
  aligned.origin = pivot - aligned.basis * center
 return aligned

func framing_limits(points: Array[Vector3], size: float, top_left: Vector3, bottom_right: Vector3) -> Vector4:
 var limits := Vector4(-INF, INF, -INF, INF)
 for point in points:
  var depth := VIEW_DEPTH - point.z * size
  limits.x = maxf(limits.x, top_left.x * depth - point.x * size)
  limits.y = minf(limits.y, bottom_right.x * depth - point.x * size)
  limits.z = maxf(limits.z, bottom_right.y * depth - point.y * size)
  limits.w = minf(limits.w, top_left.y * depth - point.y * size)
 return limits

func disable_mesh_shadows(root: Node) -> void:
 for mesh in root.find_children("*", "MeshInstance3D", true, false):
  mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
