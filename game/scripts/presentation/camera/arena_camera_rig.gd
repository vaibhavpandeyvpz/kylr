class_name ArenaCameraRig
extends Node3D

const VIEWS := ["opening", "fpv", "tpv", "death"]

var camera: Camera3D
var host: PhantomCameraHost
var cameras: Dictionary = {}
var follow_anchors: Dictionary = {}
var focus_anchors: Dictionary = {}
var active_view := ""

func _ready() -> void:
	camera = Camera3D.new()
	camera.name = "RenderCamera"
	camera.near = 0.04
	camera.far = 700.0
	add_child(camera)
	camera.current = true
	host = PhantomCameraHost.new()
	host.name = "PhantomCameraHost"
	camera.add_child(host)
	for view in VIEWS:
		var pcam := PhantomCamera3D.new()
		pcam.name = view.capitalize() + "PCam"
		pcam.tween_on_load = false
		pcam.inactive_update_mode = PhantomCamera3D.InactiveUpdateMode.NEVER
		var tween := PhantomCameraTween.new()
		tween.duration = 0.0 if view == "death" else 0.2 if view in ["fpv", "tpv"] else 0.35
		tween.transition = PhantomCameraTween.TransitionType.SINE
		pcam.tween_resource = tween
		var lens := Camera3DResource.new()
		lens.fov = 60.0
		lens.near = 0.04
		lens.far = 700.0
		pcam.camera_3d_resource = lens
		if view in ["fpv", "tpv"]:
			var anchor := Node3D.new()
			anchor.name = view.capitalize() + "Follow"
			add_child(anchor)
			follow_anchors[view] = anchor
			pcam.follow_mode = PhantomCamera3D.FollowMode.GLUED
			pcam.follow_target = anchor
		else:
			var focus := Node3D.new()
			focus.name = view.capitalize() + "Focus"
			add_child(focus)
			focus_anchors[view] = focus
			pcam.look_at_mode = PhantomCamera3D.LookAtMode.SIMPLE
			pcam.look_at_target = focus
		add_child(pcam)
		cameras[view] = pcam
	select("opening")

func select(view: String) -> void:
	if active_view == view: return
	active_view = view
	for key in cameras:
		var pcam: PhantomCamera3D = cameras[key]
		pcam.priority = 10 if key == view else 0

func set_gameplay(view: String, pose: Transform3D, target_fov: float, snap := false) -> void:
	var anchor: Node3D = follow_anchors[view]
	anchor.global_transform = pose
	var pcam: PhantomCamera3D = cameras[view]
	pcam.global_basis = pose.basis
	set_lens(pcam, target_fov)
	select(view)
	if snap and pcam.is_active(): pcam.teleport_position()

func set_cinematic(view: String, point: Vector3, focus: Vector3, target_fov := 60.0) -> void:
	var pcam: PhantomCamera3D = cameras[view]
	pcam.global_position = point
	var look_at_target: Node3D = focus_anchors[view]
	look_at_target.global_position = focus
	set_lens(pcam, target_fov)
	select(view)

func set_lens(pcam: PhantomCamera3D, target_fov: float) -> void:
	if absf(float(pcam.fov) - target_fov) > 0.05:
		pcam.fov = target_fov

func freeze_for_capture(pose: Transform3D) -> void:
	host.set_process(false)
	host.set_physics_process(false)
	camera.global_transform = pose
