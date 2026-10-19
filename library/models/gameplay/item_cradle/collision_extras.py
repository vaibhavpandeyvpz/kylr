"""Keep the fixed base and each moving claw independently addressable."""

def COLLIDER_NAME(mesh, bone):
    if bone.startswith('Clamp'):
        return 'SK_ItemCradleClaw'+bone.removeprefix('Clamp')+'Col'
    return 'SK_ItemCradleBaseCol'
