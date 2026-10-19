extends SceneTree
## Validate vertical FOV conversion against the projection's actual Y scale.
func _initialize():
	var max_old_error:=0.0
	var max_corrected_error:=0.0
	for aspect in [4.0/3.0,16.0/9.0,21.0/9.0,9.0/16.0]:
		for vertical_fov in [45.0,60.0,75.0,90.0]:
			var projection:=Projection.create_perspective(vertical_fov,aspect,.05,500.0)
			var expected:=rad_to_deg(2.0*atan(1.0/absf(projection[1].y)))
			var horizontal_fov:=projection.get_fov()
			var old_fovy:=Projection.get_fovy(horizontal_fov,projection.get_aspect())
			var corrected_fovy:=Projection.get_fovy(horizontal_fov,1.0/projection.get_aspect())
			max_old_error=maxf(max_old_error,absf(old_fovy-expected))
			max_corrected_error=maxf(max_corrected_error,absf(corrected_fovy-expected))
	print("TEMPORAL_CAMERA_FOV old_error_deg=",max_old_error," corrected_error_deg=",max_corrected_error)
	if max_old_error<20 or max_corrected_error>.0001:
		push_error("Temporal camera FOV does not match the projection");quit(1);return
	print("TEMPORAL_CAMERA_FOV_PASS")
	quit()
