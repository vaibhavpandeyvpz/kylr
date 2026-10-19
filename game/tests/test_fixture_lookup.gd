extends GutTest

func test_lookup_tracks_live_state_and_array_mutations():
	var map := ArenaMap.new()
	autofree(map)
	var first := {"id":"first","cooldown":0.0}
	var second := {"id":"second","cooldown":1.0}
	map.fixtures = [first,second]
	assert_eq(map.fixture_by_id("second"),second)
	second.cooldown = 9.0
	assert_eq(map.fixture_by_id("second").cooldown,9.0)
	map.fixtures.reverse()
	assert_eq(map.fixture_by_id("second"),second,"Moved entries remain addressable")
	map.fixtures.remove_at(0)
	assert_null(map.fixture_by_id("second"),"Removed entries cannot survive in the index")
	assert_null(map.fixture_by_id("later"))
	var later := {"id":"later","cooldown":2.0}
	map.fixtures.append(later)
	assert_eq(map.fixture_by_id("later"),later,"Missing IDs must not be negatively cached")
	map.fixtures[1] = {"id":"later","cooldown":3.0}
	assert_eq(map.fixture_by_id("later").cooldown,3.0,"Replacement state stays live")
	map.fixtures[1].id = "renamed"
	assert_null(map.fixture_by_id("later"))
	assert_eq(map.fixture_by_id("renamed").cooldown,3.0)
	map.fixtures.clear()
	assert_null(map.fixture_by_id("first"))
