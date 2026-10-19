"""Twenty-foot double-ended sibling of the authored short cargo container.
The shared scripted construction remains in ../container/model.py.
"""

# Authored runtime material classifiers; colours and geometry are unchanged.
MATERIAL_CLASSIFIERS = {
    'M_Emissive': 'Emissive',
    'M_Frame': 'Diffuse',
    'M_Joint': 'Diffuse',
    'M_Primary': 'Diffuse',
    'M_Secondary': 'Diffuse',
}
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cargo_container',HERE.parent/'container/model.py')
asset=importlib.util.module_from_spec(spec);spec.loader.exec_module(asset)
asset.HERE=HERE
asset.NAME,asset.TITLE='container_long','ContainerLong'
asset.D=6.058/asset.dimensions.PLAN[asset.NAME]
asset.DOUBLE_END=True

if __name__=='__main__':asset.main()
