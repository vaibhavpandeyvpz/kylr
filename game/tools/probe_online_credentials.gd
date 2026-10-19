extends SceneTree
func _initialize(): run.call_deferred()
func run():
	var existed := FileAccess.file_exists(OnlineCredentials.PATH)
	var previous := FileAccess.get_file_as_string(OnlineCredentials.PATH) if existed else ""
	var token := Crypto.new().generate_random_bytes(32).hex_encode()
	var saved := await OnlineCredentials.save(self,token,"http://local-probe")
	var loaded := await OnlineCredentials.load_token(self,"http://local-probe")
	var wrong := await OnlineCredentials.load_token(self,"http://different-endpoint")
	var ciphertext := FileAccess.get_file_as_string(OnlineCredentials.PATH)
	var decoded := await OnlineCredentials.transform(self,ciphertext,false)
	print("CREDENTIAL_DECRYPT bytes=",decoded.length()," json=",decoded.begins_with("{")," matches_payload=",decoded.contains(token))
	var passed := saved and loaded == token and wrong == "" and not ciphertext.contains(token)
	print("CREDENTIAL_DIAGNOSTIC saved=",saved," loaded_bytes=",loaded.length()," cipher_bytes=",ciphertext.length())
	if existed:
		var file := FileAccess.open(OnlineCredentials.PATH,FileAccess.WRITE)
		file.store_string(previous)
	else: OnlineCredentials.clear()
	print("CREDENTIAL_PROBE protected=",passed)
	quit(0 if passed else 1)
