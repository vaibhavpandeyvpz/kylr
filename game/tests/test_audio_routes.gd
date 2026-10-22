extends GutTest

func test_reused_spatial_voices_select_fixed_routes_without_changing_bus_sends():
	ArenaMix.configure()
	var sends: Array[StringName]=[]
	for index in AudioServer.bus_count: sends.append(AudioServer.get_bus_send(index))
	var stream := AudioStreamWAV.new()
	stream.format=AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate=8000
	stream.data=PackedByteArray([0,0,0,0])
	for group in [[false,false,["World","Critical","Announcer"]],[true,false,["Ambience"]],[false,true,["Voices"]]]:
		var voice := ArenaVoice.new()
		add_child_autofree(voice)
		voice.configure(0,false,group[0],group[1])
		for route in group[2]:
			var profile := AudioCues.profile("rifle")
			profile.bus=route
			voice.start("route_test",stream,profile,Vector3.ZERO,50,0,1)
			assert_eq(voice.player.bus,ArenaMix.voice_bus(0,group[0],group[1],route))
			assert_eq(AudioServer.get_bus_send(AudioServer.get_bus_index(voice.bus_name)),StringName(route))
			assert_not_null(voice.filter)
			voice.stop()
	assert_eq(AudioServer.bus_count,sends.size())
	for index in sends.size(): assert_eq(AudioServer.get_bus_send(index),sends[index])
	await wait_seconds(0.12)
