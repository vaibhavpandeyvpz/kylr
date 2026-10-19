class_name MovementPose
extends RefCounted

class TrackSample extends RefCounted:
	var track: int
	var bone: int
	var name: String
	var type: int

class ClipSample extends RefCounted:
	var animation: Animation
	var tracks: Array[TrackSample] = []

# A distance-driven lower-body layer. Combat events keep their authored upper-body timing.
var phase := 0.0
var turn_phase := 0.0
var key := ""
var state_time := 0.0
var airborne := false
var airborne_from_jump := false
var takeoff := ""
var landed := false
var air_time := 0.0
var landing_clip := "jump_down"
var samples: Dictionary = {}
var previous_pose: Dictionary = {}
var output_pose: Dictionary = {}
var blend_time := 0.0
var blend_elapsed := 0.0
var skeleton: Skeleton3D
var character_family := "tensor"

func configure(owner: Skeleton3D, family: String) -> void:
	skeleton=owner
	character_family=family

func reset() -> void:
	phase=0
	turn_phase=0
	key=""
	state_time=0
	airborne=false
	airborne_from_jump=false
	landed=false
	air_time=0
	takeoff=""
	previous_pose.clear()
	output_pose.clear()

func sample(clip: String) -> ClipSample:
	if samples.has(clip): return samples[clip]
	var animation := Assets.animation(clip,character_family)
	var result := ClipSample.new()
	result.animation = animation
	if animation:
		for track in animation.get_track_count():
			var name := String(animation.track_get_path(track)).get_slice(":",1)
			var bone := skeleton.find_bone(name)
			var lower := name in ["Root","Hips"]
			var ancestor := bone
			while ancestor >= 0 and not lower:
				lower=String(skeleton.get_bone_name(ancestor)) in ["LeftUpperLeg","RightUpperLeg"]
				ancestor=skeleton.get_bone_parent(ancestor)
			if lower and bone>=0:
				var entry := TrackSample.new()
				entry.track = track
				entry.bone = bone
				entry.name = name
				entry.type = animation.track_get_type(track)
				result.tracks.append(entry)
	samples[clip]=result
	return result

func advance(motion: Vector2, dt: float, grounded: bool, jumped: bool, charged: bool, crouched: bool, family: String, yaw_delta := 0.0, vertical_speed := 0.0) -> void:
	state_time+=dt
	var speed := motion.length()/maxf(dt,0.0001)
	var clip: String
	if not grounded:
		air_time+=dt
		if not airborne or jumped:
			state_time=0
			airborne_from_jump=jumped
			takeoff=RobotClips.takeoff(family,speed>0.2,charged) if jumped else "jump_up" if vertical_speed>0.5 else "common/falling"
		airborne=true
		landed=false
		clip=takeoff if state_time<0.22 else "jump_loop" if airborne_from_jump or vertical_speed>=-0.5 else "common/falling"
	else:
		if airborne:
			state_time=0
			landed=true
			landing_clip="common/falling_to_landing" if air_time>0.5 else "jump_down"
		air_time=0
		airborne=false
		airborne_from_jump=false
		# Moving landings blend the impact into the live stride below.
		if speed>0.15:
			clip=RobotClips.travel(motion,speed,crouched,family,0)
		elif absf(yaw_delta)/maxf(dt,0.0001)>0.35:
			clip=RobotClips.turn(crouched,yaw_delta)
		elif landed and state_time<0.28:
			clip=landing_clip
		else:
			clip=RobotClips.idle(crouched,false)
	var next := clip if "/" in clip else family+"/"+clip
	if next != key:
		if "turn_90" in next: turn_phase=0
		previous_pose=output_pose.duplicate(true)
		blend_elapsed=0
		blend_time=0.1 if not previous_pose.is_empty() else 0.0
		key=next
	var data := sample(key)
	var animation: Animation=data.animation
	if grounded and speed>0.15 and animation:
		var stride: float=animation.get_meta("stride_distance",0.0)
		if stride>0.01: phase=fposmod(phase+motion.length()/stride,1.0)
		else: phase=fposmod(phase+dt/maxf(animation.length,0.01),1.0)
	elif "turn_90" in key: turn_phase=fposmod(turn_phase+absf(yaw_delta)/(PI*0.5),1.0)

func apply(dt: float) -> void:
	if key=="" or skeleton==null: return
	var data := sample(key)
	var animation: Animation=data.animation
	if animation==null: return
	blend_elapsed+=dt
	var blend := minf(1,blend_elapsed/blend_time) if blend_time>0 else 1.0
	# The previous clip no longer contributes after the transition. Avoid
	# interpolating every lower-body track against it for the rest of the clip.
	if blend >= 1.0 and not previous_pose.is_empty(): previous_pose.clear()
	var moving := "/walk_" in key or "/run_" in key or "/sprint_" in key or "/crouch_walk_" in key
	var looping := animation.loop_mode==Animation.LOOP_LINEAR or key.ends_with("/jump_loop") or key=="common/falling"
	var time := phase*animation.length if moving else turn_phase*animation.length if "turn_90" in key else fposmod(state_time,maxf(animation.length,0.01)) if looping else minf(state_time,animation.length)
	var landing: Animation=sample(landing_clip if "/" in landing_clip else key.get_slice("/",0)+"/"+landing_clip).animation if moving and landed and state_time<0.28 else null
	var impact_weight := 0.35*(1.0-state_time/0.28) if landing else 0.0
	for entry: TrackSample in data.tracks:
		var bone: int=entry.bone
		if not output_pose.has(bone): output_pose[bone]={}
		match entry.type:
			Animation.TYPE_ROTATION_3D:
				var rotation := Quaternion.IDENTITY if entry.name=="Root" else animation.rotation_track_interpolate(entry.track,time)
				if landing and entry.name!="Root":
					var impact_track := landing.find_track(animation.track_get_path(entry.track),Animation.TYPE_ROTATION_3D)
					if impact_track>=0: rotation=rotation.slerp(landing.rotation_track_interpolate(impact_track,state_time/0.28*landing.length),impact_weight)
				if previous_pose.has(bone) and previous_pose[bone].has("rotation"): rotation=previous_pose[bone].rotation.slerp(rotation,blend)
				skeleton.set_bone_pose_rotation(bone,rotation)
				output_pose[bone].rotation=rotation
			Animation.TYPE_POSITION_3D:
				var position := animation.position_track_interpolate(entry.track,time)
				if previous_pose.has(bone) and previous_pose[bone].has("position"): position=previous_pose[bone].position.lerp(position,blend)
				skeleton.set_bone_pose_position(bone,position)
				output_pose[bone].position=position
