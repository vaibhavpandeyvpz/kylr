extends GutTest

func test_credentials_only_travel_to_https_or_loopback_services():
	var client := OnlineClient.new()
	for endpoint in ["https://accounts.example.com","http://127.0.0.1:8080","http://localhost:8080","http://[::1]:8080"]:
		client.endpoint = endpoint
		assert_true(client.secure_endpoint(),endpoint)
	for endpoint in ["http://remote.example.com","http://localhost:8080@remote.example.com","https://user:password@example.com","https://example.com?token=x","file:///secret","http://127.0.0.1:99999","http://localhost:bad","https://example.com/path"]:
		client.endpoint = endpoint
		assert_false(client.secure_endpoint(),endpoint)
	client.free()

func test_round_loading_suspends_inputs_and_uses_a_bounded_loading_deadline():
	var transport := OnlineTransport.new()
	transport.generation = "current-round"
	transport.round_ready = true
	transport.silence_deadline = 1
	transport.unacked.append({"seq":1})
	transport.preparing_round("old-round")
	assert_false(transport.building,"Stale preparation notices are ignored")
	transport.preparing_round("current-round")
	assert_true(transport.building)
	assert_false(transport.round_ready)
	assert_eq(transport.silence_deadline,0)
	assert_true(transport.unacked.is_empty())
	assert_gt(transport.connection_deadline,Time.get_ticks_msec())
	assert_lte(transport.connection_deadline,Time.get_ticks_msec()+90000)
	transport.free()
