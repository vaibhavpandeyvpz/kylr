def can_build(env, platform):
    if env["disable_navigation_3d"]:
        return False

    env.module_add_dependencies("navigation", ["csg", "gridmap"], True)
    return True


def configure(env):
    pass


def get_doc_classes():
    return ["PortalAStar3D"]


def get_doc_path():
    return "doc_classes"
