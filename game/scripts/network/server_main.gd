extends SceneTree
func _initialize():
	var transport := OnlineTransport.new()
	transport.name = "OnlineTransport"
	root.add_child.call_deferred(transport)
	transport.start_server.call_deferred()
