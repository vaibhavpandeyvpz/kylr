"""Independent leaf clips: each clip keys only its own hinge and lock bones.

Keep the paired open/close clips for existing consumers. Independent clips can
be layered without forcing the other leaf back to its closed rest pose.
"""
def independent_leaves(animations, keys):
    for side in ('left', 'right'):
        prefix=side.title()+'Door'
        leaf={bone:frames for bone,frames in keys.items()
              if bone==prefix or bone.startswith(prefix+'Bolt')}
        assert prefix in leaf
        animations['open_'+side]=(False,'BEZIER',leaf)
        animations['close_'+side]=(False,'BEZIER',{
            bone:[(96-frame,value) for frame,value in reversed(frames)]
            for bone,frames in leaf.items()})
    return animations

def controlled_bones(name,has_rear=False):
    if name in ('open_left','close_left','open_right','close_right'):
        prefix=('Left' if name.endswith('left') else 'Right')+'Door'
        return {prefix,prefix+'Bolt'}
    if name in ('open_front','close_front'):return {'Door','Lock'}
    if name in ('open_rear','close_rear'):return {'RearDoor','RearLock'}
    if has_rear and name in ('open','close'):return {'Door','Lock'}
    return None

def isolate_glb(path):
    """Remove exporter-added rest tracks from independently controlled clips.

Blender's sampled glTF exporter emits every bone even for a sparse action.
Keep the sampled hinge/lock tracks, but prevent a leaf clip resetting its peer.
The binary buffer and accessor offsets remain unchanged.
"""
    import json,struct
    from pathlib import Path
    path=Path(path);raw=path.read_bytes()
    length,kind=struct.unpack_from('<II',raw,12)
    assert kind==0x4e4f534a
    document=json.loads(raw[20:20+length])
    for animation in document.get('animations',[]):
        name=animation['name']
        allowed=controlled_bones(name,any(n.get('name')=='RearDoor' for n in document['nodes']))
        if allowed:
            animation['channels']=[channel for channel in animation['channels']
                if document['nodes'][channel['target']['node']].get('name','') in allowed]
            assert {document['nodes'][c['target']['node']]['name'] for c in animation['channels']}==allowed
    payload=json.dumps(document,separators=(',',':')).encode()
    payload+=b' '*((-len(payload))%4)
    tail=raw[20+length:]
    path.write_bytes(struct.pack('<III',0x46546c67,2,20+len(payload)+len(tail))+
        struct.pack('<II',len(payload),kind)+payload+tail)

def install_fbx_filter():
    """Filter native Blender FBX bake data before it writes curve connections."""
    from io_scene_fbx import export_fbx_bin
    if getattr(export_fbx_bin.fbx_animations_do,'independent_filter',False):return
    original=export_fbx_bin.fbx_animations_do
    def sampled(scene_data,ref_id,*args,**kwargs):
        result=original(scene_data,ref_id,*args,**kwargs)
        if result and isinstance(ref_id,tuple):
            name=ref_id[-1].name
            bones=controlled_bones(name,any(o.is_bone and o.bdata.name=='RearDoor' for o in scene_data.objects))
            if bones:
                allowed={o.key for o in scene_data.objects if o.is_bone and o.bdata.name in bones}
                for key in list(result[1]):
                    if key not in allowed:del result[1][key]
                assert result[1],('missing independent FBX tracks',name)
        return result
    sampled.independent_filter=True
    export_fbx_bin.fbx_animations_do=sampled
