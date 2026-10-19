extends SceneTree
const WEAPONS = ["pistol","rifle","minigun","rocket_launcher","lightning_gun","flamethrower","emp_gun"]
func _initialize(): call_deferred("capture")
func capture():
 var app = load("res://app.tscn").instantiate()
 root.add_child(app)
 if not app.startup_complete: await app.startup_finished
 app.prefs.values.count = 2
 app.prefs.values.name = "Framing"
 await app.start_match()
 await create_timer(23).timeout
 app.set_process(false)
 app.ui.hide()
 var game: ArenaMatch = app.match_node
 game.third_person = false
 game.fov = 60
 var robot: ArenaRobot = game.local_robot
 robot.set_physics_process(false)
 robot.protection = 0
 robot.spawn_remaining = 0
 robot.pitch = 0
 robot.wants_fire = false
 for id in WEAPONS:
  robot.equip(id)
  robot.pose("idle")
  await create_timer(0.35).timeout
  await RenderingServer.frame_post_draw
  root.get_texture().get_image().save_png("res://reports/fpv-%s.png" % id)
  print("FPV ",id," muzzle_pixel=",game.camera.unproject_position(game.first_person.gun.find_child("Muzzle*",true,false).global_position) if game.first_person.gun.find_child("Muzzle*",true,false) else "none")
  robot.pose("fire")
  robot.weapon_vfx.begin_shot()
  await create_timer(0.12).timeout
  await RenderingServer.frame_post_draw
  root.get_texture().get_image().save_png("res://reports/fpv-%s-fire.png" % id)
  if id != "pistol":
   robot.pickup_weapon = id
   robot.loaded = 1
   robot.packs = 2
   robot.start_reload()
   robot.pose("reload")
   Assets.play(robot.gun, "reload")
   await create_timer(0.8).timeout
   await RenderingServer.frame_post_draw
   root.get_texture().get_image().save_png("res://reports/fpv-%s-reload.png" % id)
   robot.reload_time = 0
 robot.equip("rifle")
 robot.pose("idle")
 robot.wants_secondary = true
 await create_timer(0.5).timeout
 await RenderingServer.frame_post_draw
 root.get_texture().get_image().save_png("res://reports/fpv-rifle-scope.png")
 robot.wants_secondary = false
 robot.pose("run_forward")
 await create_timer(0.5).timeout
 await RenderingServer.frame_post_draw
 root.get_texture().get_image().save_png("res://reports/fpv-rifle-run.png")
 robot.pose("fire")
 await create_timer(0.15).timeout
 await RenderingServer.frame_post_draw
 root.get_texture().get_image().save_png("res://reports/fpv-rifle-fire.png")
 app.ui.show()
 robot.pickup_weapon = "rifle"
 robot.loaded = Arsenal.WEAPONS.rifle.capacity
 robot.pose("idle")
 await create_timer(0.35).timeout
 await RenderingServer.frame_post_draw
 root.get_texture().get_image().save_png("res://reports/fpv-rifle-hud.png")
 app.request_quit()

