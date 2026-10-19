extends GutTest

func test_profile_roster_is_independent_of_global_random_consumption():
	var first := RandomNumberGenerator.new()
	first.seed = 120
	var colors := [Color.RED,Color.GREEN,Color.BLUE,Color.YELLOW]
	var heads_a := Arsenal.HEADS.duplicate()
	var heads_b := Arsenal.HEADS.duplicate()
	ArenaMatch.shuffle_roster(colors,first)
	ArenaMatch.shuffle_roster(heads_a,first)
	ArenaMatch.shuffle_roster(heads_b,first)
	for index in 1000: randf()
	var second := RandomNumberGenerator.new()
	second.seed = 120
	var other_colors := [Color.RED,Color.GREEN,Color.BLUE,Color.YELLOW]
	var other_a := Arsenal.HEADS.duplicate()
	var other_b := Arsenal.HEADS.duplicate()
	ArenaMatch.shuffle_roster(other_colors,second)
	ArenaMatch.shuffle_roster(other_a,second)
	ArenaMatch.shuffle_roster(other_b,second)
	assert_eq(colors,other_colors)
	assert_eq(heads_a,other_a)
	assert_eq(heads_b,other_b)
	assert_eq(heads_a.size(),Arsenal.HEADS.size())
	assert_eq(heads_b.size(),Arsenal.HEADS.size())
	for head in Arsenal.HEADS:
		assert_eq(heads_a.count(head),1)
		assert_eq(heads_b.count(head),1)

func test_normal_roster_keeps_global_shuffle_behavior():
	seed(120)
	var expected := Arsenal.HEADS.duplicate()
	expected.shuffle()
	var expected_next := randi()
	seed(120)
	var actual := Arsenal.HEADS.duplicate()
	ArenaMatch.shuffle_roster(actual)
	assert_eq(actual,expected)
	assert_eq(randi(),expected_next)
