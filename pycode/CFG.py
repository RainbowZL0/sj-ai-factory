from pathlib import Path

from pycode.utils import build_index_dict_by_id_from_list, load_yaml

DEVICE_SPEC_YAML_PATH = Path("../spec_yaml/device.yaml")
RECIPE_SPEC_YAML_PATH = Path("../spec_yaml/recipes.yaml")
INIT_BIND_OF_DEVICE_ID_AND_RECIPE_YAML_PATH = Path("../spec_yaml/init_bind_of_device_and_recipe.yaml")
INIT_STOCK_PATH = Path("../spec_yaml/init_stock.yaml")

DEVICE_SPEC_LIST = load_yaml(DEVICE_SPEC_YAML_PATH)
RECIPE_SPEC_LIST = load_yaml(RECIPE_SPEC_YAML_PATH)
INIT_RUNTIME_DEVICE_ID_AND_RECIPE_NAME_DICT = load_yaml(INIT_BIND_OF_DEVICE_ID_AND_RECIPE_YAML_PATH)


DEVICE_ID_AND_SPEC_DICT = build_index_dict_by_id_from_list(
    DEVICE_SPEC_LIST,
    "id",
)

RECIPE_NAME_AND_SPEC_DICT = build_index_dict_by_id_from_list(
    RECIPE_SPEC_LIST,
    "name",
)
