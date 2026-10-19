class_name HitPose
extends RefCounted

class TrackSample extends RefCounted:
	var track: int
	var bone: int
	var type: int
	var neutral_inverse: Quaternion
	var neutral_position: Vector3

# Add damage reactions above the waist without canceling a shot, reload or jump.
var saved: Dictionary = {}
var clips: Dictionary = {}
var tracks: Dictionary = {}

func restore(skeleton: Skeleton3D) -> void:
	for bone in saved: skeleton.set_bone_pose(bone,saved[bone])
	saved.clear()

func apply(robot) -> void:
	if robot.hit_flash<=0 or not robot.alive: return
	var family: String=Arsenal.WEAPONS[robot.equipped].animation_family
	var key: String=robot.character.animation_family+"/"+family
	if not clips.has(key):
		clips[key]={"hit":Assets.animation(family+"/hit_reaction",robot.character.animation_family),"idle":Assets.animation(family+"/idle",robot.character.animation_family)}
	var animation: Animation=clips[key].hit
	var idle: Animation=clips[key].idle
	if animation==null or idle==null: return
	var skeleton: Skeleton3D=robot.skeleton
	var root := skeleton.find_bone(robot.character.skeleton.aim_root)
	var track_key := "%s/%s/%s/%s" % [key,skeleton.get_instance_id(),skeleton.get_bone_count(),root]
	if not tracks.has(track_key):
		var entries: Array[TrackSample] = []
		for track in animation.get_track_count():
			var type := animation.track_get_type(track)
			if type not in [Animation.TYPE_ROTATION_3D,Animation.TYPE_POSITION_3D]: continue
			var name := String(animation.track_get_path(track)).get_slice(":",1)
			var bone := skeleton.find_bone(name)
			var ancestor := bone
			while ancestor>=0 and ancestor!=root: ancestor=skeleton.get_bone_parent(ancestor)
			if root<0 or ancestor!=root: continue
			var reference := idle.find_track(animation.track_get_path(track),type)
			if reference>=0:
				var entry := TrackSample.new()
				entry.track = track
				entry.bone = bone
				entry.type = type
				if type == Animation.TYPE_ROTATION_3D: entry.neutral_inverse = idle.rotation_track_interpolate(reference,0).inverse()
				else: entry.neutral_position = idle.position_track_interpolate(reference,0)
				entries.append(entry)
		tracks[track_key] = entries
	var progress := clampf(1.0-robot.hit_flash/0.2,0,1)
	var weight := 0.65*sin(PI*progress)
	var entries: Array[TrackSample] = tracks[track_key]
	for entry: TrackSample in entries:
		var track: int = entry.track
		var bone: int = entry.bone
		if not saved.has(bone): saved[bone]=skeleton.get_bone_pose(bone)
		if entry.type==Animation.TYPE_ROTATION_3D:
			var delta: Quaternion = animation.rotation_track_interpolate(track,progress*animation.length)*entry.neutral_inverse
			skeleton.set_bone_pose_rotation(bone,Quaternion.IDENTITY.slerp(delta,weight)*skeleton.get_bone_pose_rotation(bone))
		elif entry.type==Animation.TYPE_POSITION_3D:
			var delta: Vector3 = animation.position_track_interpolate(track,progress*animation.length)-entry.neutral_position
			skeleton.set_bone_pose_position(bone,skeleton.get_bone_pose_position(bone)+delta*weight)
