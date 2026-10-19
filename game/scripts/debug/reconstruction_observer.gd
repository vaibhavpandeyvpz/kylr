extends CompositorEffect
## Read-only evidence from renderer-owned reconstruction, never a filtering pass.
var expected_backend := "DLSS"
var metadata_key: StringName = &"dlss_diagnostics"
var required_feature := ""
var _mutex := Mutex.new()
var _frames := 0
var _error := ""
var _released := false
var _snapshot: Dictionary = {}

func _init():
	effect_callback_type = CompositorEffect.EFFECT_CALLBACK_TYPE_POST_OPAQUE
	access_resolved_color = true

func stats() -> Dictionary:
	_mutex.lock()
	var result := {"frames": _frames, "error": _error, "released": _released,
		"adapter": _snapshot.duplicate(true)}
	_mutex.unlock()
	for key in ["size","output_size"]:
		if result.adapter.has(key):
			var size:Vector2i=result.adapter[key]
			result.adapter[key]=[size.x,size.y]
	return result

func _render_callback(_type: int, data: RenderData):
	if _released or not _error.is_empty(): return
	var buffers: RenderSceneBuffersRD = data.get_render_scene_buffers()
	var snapshot: Dictionary = buffers.get_meta(metadata_key, {})
	if snapshot.is_empty() or int(snapshot.get("frames",0))==0: return
	var failure := ""
	if buffers.get_view_count() != 1: failure = "Reconstruction observer requires one view"
	elif snapshot.get("backend") != expected_backend or not snapshot.get("viewport_renderer", false):
		failure = "Observed a different reconstruction backend"
	elif not required_feature.is_empty() and snapshot.get("feature","") != required_feature:
		failure = "Observed a different reconstruction feature"
	_mutex.lock()
	_error = failure
	_frames += 1
	_snapshot = snapshot.duplicate(true)
	_mutex.unlock()
	if not failure.is_empty(): push_error(failure)

func release():
	enabled = false
	RenderingServer.call_on_render_thread(_release)

func _release():
	_mutex.lock()
	_released = true
	_mutex.unlock()
