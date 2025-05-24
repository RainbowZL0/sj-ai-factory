from collections import defaultdict
from typing import Dict

from pycode.dev_runtime import DevRuntime


def build_index_dict_by_id_from_list(lst, id_key_name) -> Dict:
    return {dic_i[id_key_name]: dic_i for dic_i in lst}


def build_dict_of_dev_id_and_rcp_obj(
        dict_of_dev_id_and_rcp_name: dict,
        rcp_name_and_obj_dict: dict,
):
    dic = {}
    for dev_id, rcp_name in dict_of_dev_id_and_rcp_name.items():
        dic[dev_id] = rcp_name_and_obj_dict[rcp_name]
    return dic


def build_dict_of_dev_category_and_rcp_name(recipe_spec_list):
    """
    recipe_spec_list = [
        {
            "name": "Cast_Iron",
            "device_category": "CASTER",
            "cycle_time": 60,
            "power_kw": 45.0,
            "inputs": {"IronOre": 30},
            "outputs": {"IronIngot": 30},
        },
        ...
    ]
    """
    rst = defaultdict(list)
    for dic_i in recipe_spec_list:
        device_category = dic_i["device_category"]
        rcp_name = dic_i["name"]
        rst[device_category].append(rcp_name)
    return rst


def build_dict_of_dev_id_and_dev_runtime_obj(
        device_id_and_obj_dict: dict,
        recipe_name_and_obj_dict: dict,
        runtime_device_id_and_rcp_name_dict: dict,
):
    rst = {}
    for dev_id, rcp_name in runtime_device_id_and_rcp_name_dict.items():
        dev_obj = device_id_and_obj_dict[dev_id]
        rcp_obj = recipe_name_and_obj_dict[rcp_name]
        dev_runtime = DevRuntime(dev_obj, rcp_obj)
        rst[dev_id] = dev_runtime
    return rst
