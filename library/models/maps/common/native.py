"""Reusable map construction templates; these are not architecture catalog props."""
from pathlib import Path
import importlib.util,sys
HERE=Path(__file__).resolve().parent
BRIDGE=HERE/'bridge'
sys.path.insert(0,str(HERE))

def construct(family,map_detail=False):
    folder=BRIDGE
    if family=='bridge':
        sys.path.insert(0,str(folder))
        spec=importlib.util.spec_from_file_location('map_bridge_template',folder/'model.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.build(map_detail=map_detail)
    else:
        raise ValueError("Use platform_builder.build with dimensions and proposed extensions")
    return folder
