class_name PropMotion
extends Node
## Clocks advance at physics rate; only decorative pose sampling is budgeted.
signal finished(clip: StringName)

var asset: Node3D
var channels: Dictionary = {}
var reduced_motion := false
var sample_interval := 0.0
var sample_remaining := 0.0
var skeleton: Skeleton3D

func install(root: Node3D, split_jumbotron := false, bone_prefix := "") -> void:
	asset = root
	skeleton = Assets.find(root, "Skeleton3D") as Skeleton3D
	root.add_child(self)
	var source := Assets.find(root, "AnimationPlayer") as AnimationPlayer
	var clips: Dictionary = {}
	for key in source.get_animation_list(): clips[String(key)] = source.get_animation(key)
	source.stop(not bone_prefix.is_empty())
	if split_jumbotron:
		make_channel("rotors", source, clips, "Rotor", ["spin_up", "hover", "spin_down"])
		var spots := AnimationPlayer.new()
		spots.name = "SpotAnimator"
		spots.root_node = source.root_node
		source.get_parent().add_child(spots)
		make_channel("spots", spots, clips, "Spot", ["lights_on", "flood", "show", "lights_off"])
	else: make_channel("main", source, clips, bone_prefix, ["lift_up", "lift_down"] if bone_prefix == "CargoLift" else [])

func make_channel(id: String, player: AnimationPlayer, clips: Dictionary, bone_prefix := "", actions: Array = []) -> void:
	for library in player.get_animation_library_list(): player.remove_animation_library(library)
	var library := AnimationLibrary.new()
	for key in clips:
		if not actions.is_empty() and key not in actions: continue
		var clip: Animation = clips[key].duplicate()
		clip.loop_mode = Animation.LOOP_NONE
		if not bone_prefix.is_empty():
			for track in range(clip.get_track_count()-1, -1, -1):
				if not String(clip.track_get_path(track)).get_slice(":",1).begins_with(bone_prefix): clip.remove_track(track)
		library.add_animation(key, clip)
	player.add_animation_library("", library)
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	channels[id] = {"player":player, "clip":"", "time":0.0, "loop":false, "next":"", "next_loop":false, "done":false}

func play(clip: String, loop := false, next := "", next_loop := false, channel := "main", phase := 0.0) -> void:
	var state: Dictionary = channels[channel]
	assert(state.player.has_animation(clip), "Missing machinery clip: " + clip)
	state.clip = clip
	state.time = phase
	state.loop = loop
	state.next = next
	state.next_loop = next_loop
	state.done = false
	state.player.play(clip, 0.0)
	sample(state)

func at_boundary(clip: String, channel := "main") -> void:
	var state: Dictionary = channels[channel]
	if state.done or (reduced_motion and state.loop) or is_zero_approx(state.time): play(clip, false, "", false, channel)
	else:
		state.next = clip
		state.next_loop = false

static func weapon_grip_width(payload: Node3D, height_m := 0.12) -> float:
	# The holder grips the lower receiver/handle band, not the widest barrel,
	# shroud or ammo housing elsewhere on the weapon.
	var half_width := 0.0
	for mesh in payload.find_children("*", "MeshInstance3D", true, false):
		var transform: Transform3D = payload.global_transform.affine_inverse() * mesh.global_transform
		var skeleton := mesh.get_node_or_null(mesh.skeleton) as Skeleton3D
		var binds: Array[Transform3D] = []
		if mesh.skin != null and skeleton != null:
			for bind in mesh.skin.get_bind_count():
				var bone := skeleton.find_bone(mesh.skin.get_bind_name(bind))
				if bone < 0: bone = mesh.skin.get_bind_bone(bind)
				binds.append(payload.global_transform.affine_inverse() * skeleton.global_transform * skeleton.get_bone_global_rest(bone) * mesh.skin.get_bind_pose(bind))
		for surface in mesh.mesh.get_surface_count():
			var arrays: Array = mesh.mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			if not binds.is_empty() and arrays[Mesh.ARRAY_BONES] != null:
				var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
				var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
				var influences := bones.size() / vertices.size()
				for vertex in vertices.size():
					var point := Vector3.ZERO
					for influence in influences:
						var slot := vertex * influences + influence
						if weights[slot] > 0.0: point += binds[bones[slot]] * vertices[vertex] * weights[slot]
					vertices[vertex] = point
				transform = Transform3D.IDENTITY
			var count := indices.size() if not indices.is_empty() else vertices.size()
			for triangle in range(0, count, 3):
				var points: Array[Vector3] = []
				for corner in 3:
					var index := indices[triangle + corner] if not indices.is_empty() else triangle + corner
					points.append(transform * vertices[index])
				# Authored fingers sit at +/- 5.8 and 10 cm along the gun,
				# with 1.4 cm half-thickness. Ignore parts outside their reach.
				for plane in [Vector3(1, 0, 1), Vector3(1, height_m, -1), Vector3(2, -0.114, 1), Vector3(2, 0.114, -1)]:
					var clipped: Array[Vector3] = []
					for edge in points.size():
						var a := points[edge]
						var b := points[(edge + 1) % points.size()]
						var da: float = (a[int(plane.x)] - plane.y) * plane.z
						var db: float = (b[int(plane.x)] - plane.y) * plane.z
						if da >= 0.0: clipped.append(a)
						if (da >= 0.0) != (db >= 0.0): clipped.append(a.lerp(b, da / (da - db)))
					points = clipped
				for point in points: half_width = maxf(half_width, absf(point.x))
	return maxf(0.03, half_width * 2.0)

func fit_weapon_grip(width: float) -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/gameplay/weapon_holder/weapon_holder_rig.json"))
	var rows: Array = data.grip.rows
	var lower: Dictionary = rows.front()
	var upper: Dictionary = rows.back()
	for row in rows:
		if row.width_m <= width: lower = row
		if row.width_m >= width:
			upper = row
			break
	var weight := clampf(inverse_lerp(lower.width_m,upper.width_m,width),0.0,1.0) if lower.width_m != upper.width_m else 0.0
	var player: AnimationPlayer = channels.main.player
	for name in player.get_animation_list():
		if name in ["claw_open","claw_close"]: continue
		var clip := player.get_animation(name)
		for track in clip.get_track_count():
			var bone := String(clip.track_get_path(track)).get_slice(":",1)
			if bone not in data.grip.claws or clip.track_get_type(track) != Animation.TYPE_ROTATION_3D: continue
			var angle := deg_to_rad(lerpf(lower[bone].angle_deg,upper[bone].angle_deg,weight))
			for key in clip.track_get_key_count(track):
				var rotation: Quaternion = clip.track_get_key_value(track,key)
				clip.track_set_key_value(track,key,rotation * Quaternion(Vector3.RIGHT,angle))

func set_budget(reduced: bool, distance: float) -> void:
	var changed := reduced_motion != reduced
	reduced_motion = reduced
	sample_interval = 0.0 if distance < 25.0 else 0.1 if distance < 60.0 else 0.25
	if changed:
		for id in channels:
			var state: Dictionary = channels[id]
			if state.loop and reduced_motion and not state.next.is_empty():
				var next: String = state.next
				play(next, state.next_loop, "", false, id)
			else: sample(state)

func _physics_process(dt: float) -> void:
	advance(dt)

func advance(dt: float) -> void:
	sample_remaining -= dt
	for id in channels:
		var state: Dictionary = channels[id]
		if state.clip.is_empty() or state.done: continue
		var length: float = state.player.get_animation(state.clip).length
		state.time += dt
		if state.time >= length:
			if state.loop and state.next.is_empty(): state.time = fmod(state.time, length)
			else:
				state.time = length
				sample(state) # Sample the zero-degree/final boundary before changing action.
				var completed: String = state.clip
				var next: String = state.next
				var next_loop: bool = state.next_loop
				state.done = true
				if not next.is_empty(): play(next, next_loop, "", false, id)
				finished.emit(completed)
				continue
		if sample_remaining <= 0.0 or not state.loop: sample(state)
	if sample_remaining <= 0.0: sample_remaining = sample_interval

func sample(state: Dictionary) -> void:
	if state.clip.is_empty(): return
	state.player.seek(0.0 if reduced_motion and state.loop else state.time, true)
	if skeleton: skeleton.force_update_all_bone_transforms()

func snapshot() -> Dictionary:
	var result: Dictionary = {}
	for id in channels:
		var state: Dictionary = channels[id]
		result[id] = {"clip":state.clip, "time":state.time, "loop":state.loop, "next":state.next, "next_loop":state.next_loop, "done":state.done}
	return result

func restore(states: Dictionary) -> void:
	for id in states:
		var state: Dictionary = states[id]
		if state.clip.is_empty(): continue
		play(state.clip, state.loop, state.next, state.next_loop, id, state.time)
		channels[id].done = state.done
