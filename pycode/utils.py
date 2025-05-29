import datetime
from collections import defaultdict
from pathlib import Path
from typing import Dict

from ruamel.yaml import YAML

from pycode.data_class import Recipe
from pycode.dev_runtime import DevRuntime

yaml = YAML(typ="safe")


def now_time():
    return datetime.datetime.now().strftime("%m%d_%H%M%S")


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


def build_dict_of_dev_category_and_recipe_name(
        recipe_name_and_obj_dict: Dict
):
    """
    返回的字典，说明某种类型的机器能做哪些配方。
    """
    rst = defaultdict(list)
    for rcp_name, rcp_obj in recipe_name_and_obj_dict.items():
        rcp_obj: Recipe
        device_category = rcp_obj.device_category
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


def load_yaml(file_path: Path):
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.load(file)


def build_dict_of_recipe_name_and_obj(
        recipe_name_and_spec_dict,
        whether_convert_to_one_second_of_cycle_time: bool
):
    rst = {}
    for rcp_name, rcp_dict in recipe_name_and_spec_dict.items():
        rcp_obj = Recipe(**rcp_dict)
        if whether_convert_to_one_second_of_cycle_time:
            c_time = rcp_obj.cycle_time
            divide_dict_values_by(c_time, rcp_obj.inputs)
            divide_dict_values_by(c_time, rcp_obj.outputs)
            rcp_obj.cycle_time = 1
        rst[rcp_name] = rcp_obj
    return rst


def divide_dict_values_by(x, dic: dict):
    for k, v in dic.items():
        dic[k] = v / x
