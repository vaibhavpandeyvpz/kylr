extends SceneTree
## Inspect capability after native startup; no reconstruction quality claim.

func _initialize() -> void:
	run.call_deferred()

func run() -> void:
	for frame in 3:
		await process_frame
	var expected := OS.get_cmdline_user_args().has("--expect-dlss")
	var supported := false
	var rr_supported := false
	var fg_supported := false
	if Engine.has_singleton("Streamline"):
		var streamline := Engine.get_singleton("Streamline")
		supported = streamline.get_capability(ClassDB.class_get_integer_constant("Streamline", "STREAMLINE_CAPABILITY_DLSS"))
		rr_supported = streamline.get_capability(ClassDB.class_get_integer_constant("Streamline", "STREAMLINE_CAPABILITY_DLSS_RR"))
		fg_supported = streamline.get_capability(ClassDB.class_get_integer_constant("Streamline", "STREAMLINE_CAPABILITY_DLSS_G"))
	print("STREAMLINE_STARTUP ", JSON.stringify({"dlss": supported, "rr": rr_supported, "frame_generation": fg_supported, "expected": expected}))
	if supported != expected or rr_supported != expected:
		push_error("Unexpected Streamline startup capabilities")
		quit(3)
		return
	if OS.get_cmdline_user_args().has("--module-check"):
		print("STREAMLINE_MODULE_CHECK_READY pid=", OS.get_process_id())
		await create_timer(3.0).timeout
	print("STREAMLINE_STARTUP_PASS")
	quit()
