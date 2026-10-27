class_name AimPose
extends RefCounted

class BoneSample extends RefCounted:
	var bone: int
	var torso := false
	var has_rotation := false
	var has_position := false
	var has_neutral_rotation := false
	var has_neutral_position := false
	var rotation_a: Quaternion
	var rotation_b: Quaternion
	var neutral_inverse: Quaternion
	var position_a: Vector3
	var position_b: Vector3
	var neutral_position: Vector3

var saved: Dictionary = {}
var samples: Dictionary = {}
var skeleton_layout: Dictionary = {}
# Bind the seven authored pitch samples once; recoil and hip compensation remain live.
var bindings: Dictionary = {}

func bind_samples(data: Dictionary, key: String, a: Dictionary, b: Dictionary, neutral: Dictionary) -> Array[BoneSample]:
	if bindings.has(key): return bindings[key]
	var entries: Array[BoneSample] = []
	for entry in data.bones:
		var name: String = entry.name
		if not a.has(name) or not b.has(name): continue
		var result := BoneSample.new()
		result.bone = entry.bone
		result.torso = name in ["Spine","Chest","UpperChest","Neck","Head"]
		if a[name].has("rotation") and b[name].has("rotation"):
			result.has_rotation = true
			result.rotation_a = a[name].rotation
			result.rotation_b = b[name].rotation
			if neutral.has(name) and neutral[name].has("rotation"):
				result.has_neutral_rotation = true
				result.neutral_inverse = neutral[name].rotation.inverse()
		if a[name].has("position") and b[name].has("position"):
			result.has_position = true
			result.position_a = a[name].position
			result.position_b = b[name].position
			if neutral.has(name) and neutral[name].has("position"):
				result.has_neutral_position = true
				result.neutral_position = neutral[name].position
		entries.append(result)
	bindings[key] = entries
	return entries

func layout(skeleton: Skeleton3D, root_name: String) -> Dictionary:
	var id := skeleton.get_instance_id()
	if skeleton_layout.get("id",0) == id and skeleton_layout.get("count",0) == skeleton.get_bone_count() and skeleton_layout.root_name == root_name:
		return skeleton_layout
	var root := skeleton.find_bone(root_name)
	bindings.clear()
	var bones: Array = []
	for bone in skeleton.get_bone_count():
		var ancestor := bone
		while ancestor >= 0 and ancestor != root: ancestor = skeleton.get_bone_parent(ancestor)
		if root >= 0 and ancestor == root:
			bones.append({"bone":bone,"name":String(skeleton.get_bone_name(bone))})
	var chain: Array[int] = []
	var rests: Dictionary = {}
	var parent := skeleton.get_bone_parent(root) if root >= 0 else -1
	var cursor := parent
	while cursor >= 0:
		chain.push_front(cursor)
		rests[cursor]=skeleton.get_bone_rest(cursor)
		cursor = skeleton.get_bone_parent(cursor)
	skeleton_layout = {"id":id,"count":skeleton.get_bone_count(),"root_name":root_name,"root":root,"parent":parent,"bones":bones,"chain":chain,"rests":rests}
	return skeleton_layout

func restore(skeleton: Skeleton3D):
	for bone in saved: skeleton.set_bone_pose(bone, saved[bone])
	saved.clear()

func sample(family: String, weapon_family: String, angle: int) -> Dictionary:
	var clip := "aim_level" if angle == 0 else "aim_%s%d" % ["up" if angle > 0 else "down", absi(angle)]
	var key := family + "/" + weapon_family + "/" + clip
	if samples.has(key): return samples[key]
	var animation := Assets.animation(weapon_family + "/" + clip, family)
	var result: Dictionary = {}
	if animation:
		for track in animation.get_track_count():
			var bone := String(animation.track_get_path(track)).get_slice(":", 1)
			if not result.has(bone): result[bone] = {}
			match animation.track_get_type(track):
				Animation.TYPE_ROTATION_3D: result[bone].rotation = animation.rotation_track_interpolate(track, 0)
				Animation.TYPE_POSITION_3D: result[bone].position = animation.position_track_interpolate(track, 0)
	samples[key] = result
	return result

func apply(robot, pitch_radians: float):
	var skeleton: Skeleton3D = robot.skeleton
	var degrees := clampf(rad_to_deg(pitch_radians), -45, 45)
	var lower := int(floor(degrees / 15.0)) * 15
	var upper := mini(lower + 15, 45)
	var blend := (degrees - lower) / 15.0
	var family: String = Arsenal.WEAPONS[robot.equipped].animation_family
	var a := sample(robot.character.animation_family, family, lower)
	var b := sample(robot.character.animation_family, family, upper)
	var neutral := sample(robot.character.animation_family, family, 0)
	var data := layout(skeleton,robot.character.skeleton.aim_root)
	var root: int = data.root
	var firing: bool = robot.anim_state.ends_with("/fire")
	var preserve_event: bool = firing or robot.hit_flash>0
	var pistol_firing := family == "pistol" and firing
	var binding_key: String = "%s/%s/%d" % [robot.character.animation_family,family,lower]
	for entry: BoneSample in bind_samples(data,binding_key,a,b,neutral):
		var bone: int = entry.bone
		# Pistol fire was retargeted from a rifle stance. Keep the pistol's aimed
		# torso/head reference while retaining the shot motion in shoulders/arms.
		var pistol_fire_torso: bool = pistol_firing and entry.torso
		var preserve_bone_event := preserve_event and not pistol_fire_torso
		var original:=skeleton.get_bone_pose(bone)
		if entry.has_rotation:
			var aimed: Quaternion=entry.rotation_a.slerp(entry.rotation_b,blend)
			if preserve_bone_event and entry.has_neutral_rotation:
				aimed=aimed*entry.neutral_inverse*skeleton.get_bone_pose_rotation(bone)
			if not skeleton.get_bone_pose_rotation(bone).is_equal_approx(aimed):
				saved[bone]=original
				skeleton.set_bone_pose_rotation(bone, aimed)
		if entry.has_position:
			var aimed: Vector3=entry.position_a.lerp(entry.position_b,blend)
			if preserve_bone_event and entry.has_neutral_position:
				aimed+=skeleton.get_bone_pose_position(bone)-entry.neutral_position
			if not original.origin.is_equal_approx(aimed):
				saved[bone]=original
				skeleton.set_bone_pose_position(bone, aimed)
	# Keep the authored aim frame above the waist while locomotion animates the hips.
	if root >= 0:
		var parent: int = data.parent
		var reference := Quaternion.IDENTITY
		var parent_frame:=Transform3D.IDENTITY
		for bone in data.chain:
			parent_frame=parent_frame*data.rests[bone]*skeleton.get_bone_pose(bone)
			var name := String(skeleton.get_bone_name(bone))
			reference *= neutral[name].rotation if neutral.has(name) and neutral[name].has("rotation") else skeleton.get_bone_pose_rotation(bone)
		if parent >= 0:
			# Reading a dirty global pose would flush every collision attachment
			# before the aim root has its final pose. Compose the short chain locally.
			var actual := parent_frame.basis.get_rotation_quaternion()
			var current:=skeleton.get_bone_pose_rotation(root)
			var compensated:=actual.inverse()*reference*current
			if not current.is_equal_approx(compensated):
				if not saved.has(root):saved[root]=skeleton.get_bone_pose(root)
				skeleton.set_bone_pose_rotation(root,compensated)
	skeleton.force_update_all_bone_transforms()
