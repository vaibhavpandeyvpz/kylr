extends GutTest

class Actor extends RefCounted:
	var alive := true
	var hit_flash := 0.1
	var equipped := "pistol"
	var character := ContentRegistry.character("tensor")
	var skeleton: Skeleton3D

func test_cached_neutral_samples_preserve_every_weapon_family_reaction():
	var body := Assets.model("characters","tensor")
	add_child_autofree(body)
	var actor := Actor.new()
	actor.skeleton = Assets.find(body,"Skeleton3D")
	var pose := HitPose.new()
	var families := {}
	for weapon in Arsenal.WEAPONS:
		var family: String = Arsenal.WEAPONS[weapon].animation_family
		if families.has(family): continue
		families[family] = true
		actor.equipped = weapon
		var hit := Assets.animation(family+"/hit_reaction")
		var idle := Assets.animation(family+"/idle")
		for progress in [.08,.5,.92]:
			pose.restore(actor.skeleton)
			var before: Array[Transform3D] = []
			for bone in actor.skeleton.get_bone_count(): before.append(actor.skeleton.get_bone_pose(bone))
			actor.hit_flash = .2*(1.0-progress)
			pose.apply(actor)
			var weight: float = .65*sin(PI*progress)
			var checked := 0
			for track in hit.get_track_count():
				var bone := actor.skeleton.find_bone(String(hit.track_get_path(track)).get_slice(":",1))
				if not pose.saved.has(bone): continue
				var type := hit.track_get_type(track)
				var reference := idle.find_track(hit.track_get_path(track),type)
				if reference<0: continue
				if type == Animation.TYPE_ROTATION_3D:
					var delta := hit.rotation_track_interpolate(track,progress*hit.length)*idle.rotation_track_interpolate(reference,0).inverse()
					var expected := Quaternion.IDENTITY.slerp(delta,weight)*before[bone].basis.get_rotation_quaternion()
					assert_almost_eq(absf(expected.dot(actor.skeleton.get_bone_pose_rotation(bone))),1.0,.00001,family+" rotation")
					checked += 1
				elif type == Animation.TYPE_POSITION_3D:
					var expected := before[bone].origin+(hit.position_track_interpolate(track,progress*hit.length)-idle.position_track_interpolate(reference,0))*weight
					assert_lt(expected.distance_to(actor.skeleton.get_bone_pose_position(bone)),.00001,family+" position")
					checked += 1
			assert_gt(checked,0)
	pose.restore(actor.skeleton)
