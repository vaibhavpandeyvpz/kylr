class_name OnlineCredentials
extends RefCounted
const PATH := "user://online-session.bin"
# Only ciphertext touches disk. The credential and encrypted blob travel through
# stdin/stdout, never command-line arguments, environment variables or temp files.
static func transform(tree: SceneTree, payload: String, protect: bool) -> String:
	if OS.get_name() != "Windows": return ""
	var operation := "Protect" if protect else "Unprotect"
	var decode := "[Text.Encoding]::UTF8.GetBytes($line)" if protect else "[Convert]::FromBase64String($line)"
	var encode := "[Convert]::ToBase64String($result)" if protect else "[Text.Encoding]::UTF8.GetString($result)"
	var code := "Add-Type -AssemblyName System.Security; try { $line=[Console]::ReadLine(); $bytes="+decode+"; $result=[Security.Cryptography.ProtectedData]::"+operation+"($bytes,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser); [Console]::WriteLine("+encode+") } catch { exit 1 }"
	var process := OS.execute_with_pipe("powershell.exe",["-NoProfile","-NonInteractive","-WindowStyle","Hidden","-EncodedCommand",Marshalls.raw_to_base64(code.to_utf16_buffer())],false)
	if process.is_empty(): return ""
	process.stdio.store_line(payload)
	process.stdio.flush()
	var output := ""
	var deadline := Time.get_ticks_msec()+5000
	while Time.get_ticks_msec() < deadline:
		output += process.stdio.get_buffer(8192).get_string_from_utf8()
		if not OS.is_process_running(process.pid): break
		await tree.process_frame
	if OS.is_process_running(process.pid): OS.kill(process.pid)
	output += process.stdio.get_buffer(8192).get_string_from_utf8()
	process.stdio.close()
	process.stderr.close()
	return output.strip_edges()

static func save(tree: SceneTree, token: String, endpoint: String) -> bool:
	var encrypted := await transform(tree,JSON.stringify({"token":token,"endpoint":endpoint}),true)
	if encrypted == "": clear(); return false
	var file := FileAccess.open(PATH,FileAccess.WRITE)
	if file == null: return false
	file.store_string(encrypted)
	file.close()
	return true

static func load_token(tree: SceneTree, endpoint: String) -> String:
	if not FileAccess.file_exists(PATH): return ""
	var decoded := await transform(tree,FileAccess.get_file_as_string(PATH),false)
	if decoded == "": return ""
	var record = JSON.parse_string(decoded)
	if not record is Dictionary or record.get("endpoint","") != endpoint: return ""
	return record.get("token","")

static func clear():
	if FileAccess.file_exists(PATH): DirAccess.remove_absolute(ProjectSettings.globalize_path(PATH))
