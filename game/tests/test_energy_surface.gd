extends GutTest

func test_surface_follows_native_meshes_for_all_heads_and_protection_states():
 var game:=ArenaMatch.new()
 game.online=true
 add_child_autofree(game)
 await wait_physics_frames(3)
 game.authority=false;game.phase="Active"
 for head in ContentRegistry.character("tensor").heads:
  var robot: ArenaRobot=game.add_robot(game.robots.size(),"Surface probe",0,true,head)
  robot.spawn_remaining=0;robot.protection=0;robot.sh=100
  robot._process(0)
  assert_true(robot.surface_active)
  assert_eq(robot.surface_material.get_shader_parameter("surface_offset"),0.05)
  assert_eq(robot.surface_material.get_shader_parameter("tint"),robot.tint)
  for mesh in robot.surface_meshes:
   assert_eq(mesh.material_overlay,robot.surface_material)
   assert_not_null(mesh.skin,"Reuse the native skinned mesh")
  robot.body.hide()
  for mesh in robot.surface_meshes:assert_false(mesh.is_visible_in_tree())
  robot.body.show()
  robot.sh=0;robot._process(0)
  assert_false(robot.surface_active)
  robot.protection=1;robot._process(0)
  assert_true(robot.surface_active)
  robot.spawn_remaining=1;robot._process(0)
  assert_false(robot.surface_active)
  robot.spawn_remaining=0;robot.alive=false;robot._process(0)
  assert_false(robot.surface_active)
  for mesh in robot.surface_meshes:assert_null(mesh.material_overlay)

func test_damage_colors_survive_authority_events_and_snapshots():
 var game:=ArenaMatch.new()
 game.online=true
 add_child_autofree(game)
 await wait_physics_frames(3)
 game.phase="Active"
 var attacker: ArenaRobot=game.add_robot(0,"Attacker",0,true,"raptor")
 var victim: ArenaRobot=game.add_robot(1,"Victim",1,true,"projector")
 victim.spawn_remaining=0;victim.protection=0;attacker.protection=0
 game.replicating=true
 var colors={"lightning_gun":"357dff","pulse_gun":"37edff","bio_rifle":"58ff69","pistol":"ffe24d","rifle":"ffe24d","minigun":"ffe24d","rocket_launcher":"ff3535","grenade_launcher":"ff3535","flak_cannon":"ff8c2e","flamethrower":"ff8c2e","emp_gun":"a6abb3"}
 for weapon in colors:
  victim.ah=100;victim.sh=100
  game.elapsed+=.11
  assert_true(victim.hit(1,attacker,weapon))
  assert_eq(victim.surface_material.get_shader_parameter("hit_tint"),Color(colors[weapon]))
  assert_gt(victim.surface_material.get_shader_parameter("hit_strength"),0.0)
  assert_eq(victim.network_state().hit_weapon,weapon)
  var damage_events=game.presentation_events.filter(func(event):return event.kind=="damage")
  assert_eq(damage_events.back().weapon,weapon)
 assert_eq(EnergySurface.weapon_color("rifle_headshot"),Color("ffe24d"),"Rifle headshots retain the rifle shot color")
 assert_true(victim.hit(1,victim,"rocket_launcher"))
 var snapshot: Dictionary=victim.network_state()
 victim.last_hit_weapon="pistol"
 victim.restore_network(snapshot)
 assert_eq(victim.surface_material.get_shader_parameter("hit_tint"),Color("ff3535"),"Snapshot-only self damage retains its accepted weapon color")
 var transport:=OnlineTransport.new()
 transport.game=game
 add_child_autofree(transport)
 transport.apply_presentation({"kind":"damage","victim":1,"attacker":0,"source":Vector3.ZERO,"amount":1.0,"weapon":"pulse_gun"})
 assert_eq(victim.surface_material.get_shader_parameter("hit_tint"),Color("37edff"))
 victim.sh=0;victim.protection=0;victim.hit_flash=0
 victim._process(0)
 assert_false(victim.surface_active,"A hit-only surface expires with feedback")
 game.reduced_motion=true;victim.sh=100;victim._process(0)
 assert_eq(victim.surface_material.get_shader_parameter("motion_enabled"),false)
