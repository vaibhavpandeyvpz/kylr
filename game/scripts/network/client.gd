class_name OnlineClient
extends Node
signal changed
var endpoint := "http://127.0.0.1:8080"
var access := ""
var refresh := ""
var expires := 0.0
var player: Dictionary = {}
var refreshing := false
var restored := false
var remembered := false

func _ready():
	endpoint = str(ProjectSettings.get_setting("network/services/api_url",endpoint)).trim_suffix("/")
	var configured := OS.get_environment("KYLR_API_URL")
	if configured != "": endpoint = configured.trim_suffix("/")

func request(route: String, method := HTTPClient.METHOD_GET, data: Dictionary = {}, authenticate := true) -> Dictionary:
	if not secure_endpoint(): return failure("Online services require an HTTPS address. HTTP is allowed only for local testing.")
	if authenticate and expires < Time.get_unix_time_from_system()+30:
		var renewed := await renew()
		if renewed.has("error"): return renewed
	var http := HTTPRequest.new()
	# Free API instances can need about a minute to wake before the first response.
	http.timeout = 75
	add_child(http)
	var headers := PackedStringArray(["Content-Type: application/json"])
	if authenticate: headers.append("Authorization: Bearer "+access)
	var error := http.request(endpoint+route,headers,method,JSON.stringify(data) if method != HTTPClient.METHOD_GET else "")
	if error != OK: http.queue_free(); return failure("The account service could not be reached.")
	var response = await http.request_completed
	http.queue_free()
	if response[0] != HTTPRequest.RESULT_SUCCESS: return failure("The account service did not respond. It may be starting; retry shortly.")
	var body = JSON.parse_string(response[3].get_string_from_utf8())
	if not body is Dictionary: return failure("The account service returned an invalid response.")
	if response[1] >= 400 and not body.has("error"): return failure("The account request was not accepted.")
	return body

func failure(text: String) -> Dictionary: return {"error":{"code":"CONNECTION_FAILED","message":text}}

func secure_endpoint() -> bool:
	if endpoint.contains("@") or endpoint.contains("?") or endpoint.contains("#") or endpoint.contains(" ") or endpoint.contains("\n") or endpoint.contains("\r"): return false
	if endpoint.begins_with("https://"): return endpoint.trim_prefix("https://").length() > 0 and not endpoint.trim_prefix("https://").contains("/")
	if not endpoint.begins_with("http://"): return false
	var origin := endpoint.trim_prefix("http://")
	for host in ["localhost","127.0.0.1","[::1]"]:
		if origin == host: return true
		if origin.begins_with(host+":"):
			var port := origin.trim_prefix(host+":")
			return port.is_valid_int() and int(port) > 0 and int(port) <= 65535
	return false

func accept(envelope: Dictionary):
	access = envelope.access_token
	refresh = envelope.refresh_token
	expires = envelope.expires_at
	player = envelope.player
	remembered = await OnlineCredentials.save(get_tree(),refresh,endpoint)
	changed.emit()

func restore() -> Dictionary:
	if restored: return {"player":player}
	restored = true
	refresh = await OnlineCredentials.load_token(get_tree(),endpoint)
	if refresh == "": return {}
	return await renew()

func renew() -> Dictionary:
	while refreshing: await get_tree().process_frame
	if expires > Time.get_unix_time_from_system()+30: return {"player":player}
	if refresh == "": return failure("Sign in to continue.")
	refreshing = true
	var response := await request("/v1/sessions/refresh",HTTPClient.METHOD_POST,{"refresh_token":refresh},false)
	if not response.has("error"): await accept(response)
	elif response.error.code == "SESSION_EXPIRED": forget()
	refreshing = false
	return response

func sign_in(username: String, password: String, display_name := "", register := false) -> Dictionary:
	var registering := register or display_name != ""
	var data := {"username":username,"password":password}
	if registering: data.display_name = display_name
	var response := await request("/v1/accounts" if registering else "/v1/sessions",HTTPClient.METHOD_POST,data,false)
	if not response.has("error"): await accept(response)
	return response

func save_loadout(loadout: Dictionary) -> Dictionary:
	var response := await request("/v1/me/loadout",HTTPClient.METHOD_PUT,loadout)
	if response.has("player"): player = response.player; changed.emit()
	return response

func logout():
	if access != "": await request("/v1/sessions",HTTPClient.METHOD_DELETE)
	forget()

func forget():
	access = ""
	refresh = ""
	expires = 0
	player.clear()
	OnlineCredentials.clear()
	changed.emit()
