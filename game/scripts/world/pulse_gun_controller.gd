class_name PulseGunController
extends Node

var game
var asset: Node3D
var team := 0
var cooldown := 0.0
var skeleton: Skeleton3D
var animator: AnimationPlayer
var yaw_bone := -1
var yaw_axis := Vector3.UP
var yaw_rest_pose := Quaternion.IDENTITY
var muzzle: Node3D
var aim_clip: String
var settings: Dictionary
var reference_forward := Vector3.FORWARD

func install(model: Node3D, world, owner_team: int) -> void:
	asset=model;game=world;team=owner_team;settings=game.map.config.pulse_gun
	asset.add_child(self)
	skeleton=Assets.find(asset,"Skeleton3D") as Skeleton3D
	animator=Assets.find(asset,"AnimationPlayer") as AnimationPlayer
	muzzle=Assets.socket(asset,"Muzzle")
	yaw_bone=skeleton.find_bone("Yaw")
	yaw_axis=skeleton.get_bone_global_rest(yaw_bone).basis.inverse()*Vector3.UP
	for key in animator.get_animation_list():
		if String(key).get_slice("/",String(key).count("/")).ends_with("aim"):aim_clip=key
	assert(not aim_clip.is_empty(),"Pulse gun needs its baked aim/piston action")
	animator.play(aim_clip);animator.seek(0,true);animator.pause()
	yaw_rest_pose=skeleton.get_bone_pose_rotation(yaw_bone)
	skeleton.force_update_all_bone_transforms()
	reference_forward=-Assets.socket_world_transform(muzzle).basis.z

func nearest_enemy():
	var best=null
	var best_distance: float = settings.range
	for robot in game.robots:
		if robot.team==team or not robot.alive or robot.spawn_remaining>0:continue
		var distance: float=asset.global_position.distance_to(robot.global_position)
		if distance<=best_distance:best=robot;best_distance=distance
	return best

func _physics_process(dt: float) -> void:
	if not game.authority or game.phase!="Active" or game.match_type not in settings.enabled_match_types:return
	cooldown=maxf(0,cooldown-dt)
	var target=nearest_enemy()
	if target==null:return
	var direction: Vector3=(target.eye()-asset.global_position).normalized()
	var bearing:=Vector3(reference_forward.x,0,reference_forward.z).normalized().signed_angle_to(Vector3(direction.x,0,direction.z).normalized(),Vector3.UP)
	animator.play(aim_clip);animator.seek(0,true);animator.pause()
	skeleton.set_bone_pose_rotation(yaw_bone,yaw_rest_pose*Quaternion(yaw_axis,bearing))
	skeleton.force_update_all_bone_transforms()
	var pitch:=0.0
	# Aim from the actual muzzle, retaining the native barrel/piston action.
	# Re-evaluate its moving origin instead of measuring from the ground anchor.
	for iteration in 3:
		var frame:=Assets.socket_world_transform(muzzle)
		var desired: Vector3=(target.eye()-frame.origin).normalized()
		var forward: Vector3=-frame.basis.z.normalized()
		pitch=clampf(pitch+rad_to_deg(asin(desired.y)-asin(forward.y)),0,60)
		animator.seek(pitch/30.0,true)
		skeleton.set_bone_pose_rotation(yaw_bone,yaw_rest_pose*Quaternion(yaw_axis,bearing))
		skeleton.force_update_all_bone_transforms()
	var muzzle_frame:=Assets.socket_world_transform(muzzle)
	var from: Vector3=muzzle_frame.origin
	var aim: Vector3=(target.eye()-from).normalized()
	if cooldown>0 or not game.combat.clear(from,target.eye()):return
	if (-muzzle_frame.basis.z).dot(aim)<cos(deg_to_rad(6)):return
	cooldown=float(settings.interval)
	var shot_settings:=settings.duplicate(true)
	shot_settings["owner_team"]=team
	var projectile := BallisticProjectile.launch(game,null,"pulse_gun",from,aim,shot_settings)
	for collider in asset.find_children("*","CollisionObject3D",true,false):
		projectile.extra_exclusions.append(collider.get_rid())
	game.audio.cue("pulse_gun",from)
