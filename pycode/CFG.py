from pathlib import Path

from pycode.utils import build_index_dict_by_id_from_list, load_yaml

DEVICE_SPEC_YAML_PATH = Path("../spec_yaml/device.yaml")
RECIPE_SPEC_YAML_PATH = Path("../spec_yaml/recipes.yaml")
INIT_BIND_OF_DEVICE_ID_AND_RECIPE_YAML_PATH = Path("../spec_yaml/init_bind_of_device_and_recipe.yaml")
INIT_STOCK_PATH = Path("../spec_yaml/init_stock.yaml")
INIT_PRICE_PATH = Path("../spec_yaml/init_price.yaml")
INIT_ORDER_PATH = Path("../spec_yaml/init_order.yaml")
INIT_MONEY_PATH = Path("../spec_yaml/init_money.yaml")

DEVICE_SPEC_LIST = load_yaml(DEVICE_SPEC_YAML_PATH)
RECIPE_SPEC_LIST = load_yaml(RECIPE_SPEC_YAML_PATH)
INIT_BIND_OF_DEVICE_ID_AND_RECIPE_NAME_DICT = load_yaml(INIT_BIND_OF_DEVICE_ID_AND_RECIPE_YAML_PATH)
INIT_STOCK_LIST = load_yaml(INIT_STOCK_PATH)
INIT_PRICE_LIST = load_yaml(INIT_PRICE_PATH)
INIT_ORDER_LIST = load_yaml(INIT_ORDER_PATH)
INIT_MONEY = load_yaml(INIT_MONEY_PATH)["money"]

DEVICE_ID_AND_SPEC_DICT = build_index_dict_by_id_from_list(
    DEVICE_SPEC_LIST,
    "id",
)
RECIPE_NAME_AND_SPEC_DICT = build_index_dict_by_id_from_list(
    RECIPE_SPEC_LIST,
    "name",
)
INIT_STOCK_NAME_AND_SPEC_DICT = build_index_dict_by_id_from_list(
    INIT_STOCK_LIST,
    "name",
)
INIT_PRICE_NAME_AND_SPEC_DICT = build_index_dict_by_id_from_list(
    INIT_PRICE_LIST,
    "name",
)
