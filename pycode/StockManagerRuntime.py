from collections import defaultdict

from pycode.data_class import MaterialStock


class StockManagerRuntime:
    def __init__(self, init_stock_name_and_spec_dict):
        # 字典，材料名 -> 材料obj
        self.runtime_stock_name_and_obj_dict = {
            mtrl_name: MaterialStock(**mtrl_dict)
            for mtrl_name, mtrl_dict in init_stock_name_and_spec_dict.items()
        }

    def get_obj_by_name(self, name):
        return self.runtime_stock_name_and_obj_dict[name]

    def add_stock(self, name: str, qty: float):
        self.get_obj_by_name(name).quantity += qty

    def try_remove_stock(self, name, qty):
        """返回实际卖了多少量"""
        stock_obj = self.get_obj_by_name(name)
        if stock_obj.quantity < qty:
            removed_stock_qty = stock_obj.quantity
            stock_obj.quantity = 0
            return removed_stock_qty
        else:
            stock_obj.quantity -= qty
            return qty

    def get_names(self) -> list:
        return list(self.runtime_stock_name_and_obj_dict.keys())

    def get_items(self):
        return self.runtime_stock_name_and_obj_dict.items()

    def get_objs(self):
        return self.runtime_stock_name_and_obj_dict.values()

    def get_env_status(self):
        rst = defaultdict(list)
        for obj in self.get_objs():
            rst["name"].append(obj.name)
            rst["quantity"].append(obj.quantity)

        return rst
