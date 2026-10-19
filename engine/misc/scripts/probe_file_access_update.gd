extends SceneTree

# Regression fixture for update streams with cached reads and in-cache seeks.
func _initialize() -> void:
	var failures: Array[String] = []
	var original := PackedByteArray()
	original.resize(65573)
	for i in original.size():
		original[i] = (i * 17 + 3) % 251
	var path := "user://file_access_update_probe.bin"
	for mode in [FileAccess.READ_WRITE, FileAccess.WRITE_READ]:
		for operation in ["seek_write", "write_read", "resize"]:
			var initial := FileAccess.open(path, FileAccess.WRITE)
			initial.store_buffer(original)
			initial.close()
			var file := FileAccess.open(path, mode)
			if mode == FileAccess.WRITE_READ:
				file.store_buffer(original)
				file.seek(0)
			file.get_32()
			var expected := original.duplicate()
			if operation == "seek_write":
				file.seek(8)
				file.store_32(0x12345678)
				expected.encode_u32(8, 0x12345678)
			elif operation == "write_read":
				file.store_32(0x12345678)
				expected.encode_u32(4, 0x12345678)
				if file.get_32() != expected.decode_u32(8) or file.get_position() != 12:
					failures.append("%s/write_read cursor" % mode)
			else:
				if file.resize(original.size() - 1) != OK:
					failures.append("%s/resize error" % mode)
				expected.resize(original.size() - 1)
				if file.get_position() != 4 or file.get_32() != expected.decode_u32(4):
					failures.append("%s/resize cursor" % mode)
			file.seek(0)
			if file.get_buffer(expected.size()) != expected or file.get_length() != expected.size():
				failures.append("%s/%s content" % [mode, operation])
			file.close()
			if FileAccess.get_file_as_bytes(path) != expected:
				failures.append("%s/%s persisted content" % [mode, operation])
	DirAccess.remove_absolute(path)
	print("FILE_ACCESS_UPDATE_RESULT ", JSON.stringify({"cases": 6, "failures": failures, "passed": failures.is_empty()}))
	quit(0 if failures.is_empty() else 1)
