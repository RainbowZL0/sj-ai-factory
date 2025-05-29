# 轮次计时判断订单是否due了
import bisect
import random
from collections import defaultdict

import numpy as np

from pycode.data_class import Order


def get_runtime_order_obj_list(init_order_list) -> list:
    rst = [
        Order(**order_dict)
        for order_dict in init_order_list
    ]
    return sorted(rst)


class OrderManagerRuntime:
    def __init__(self, init_order_list: list):
        self.runtime_order_obj_list = get_runtime_order_obj_list(init_order_list)
        # TODO
        self.tst_random_add_order(1500)

    def add_order_obj(self, order_obj: Order):
        bisect.insort(self.runtime_order_obj_list, order_obj)

    def __getitem__(self, idx):
        return self.runtime_order_obj_list[idx]

    def __setitem__(self, idx, order_obj):
        self.runtime_order_obj_list[idx] = order_obj

    def __len__(self):
        return len(self.runtime_order_obj_list)

    def get_raw_list(self):
        return self.runtime_order_obj_list

    def tick_due_time(self):
        # TODO self.dt 时间步大于1的支持, 后期实现，应该用不到
        for o in self.get_raw_list():
            o: Order
            o.due_time -= 1

    def pop_due_orders(self) -> list[Order]:
        """在tick_due_time之后，检查哪些订单到期要交付了，把它们从订单等待队列里弹出"""
        due_orders = []
        while self.get_raw_list():
            o: Order = self[0]
            if o.due_time <= 0:
                due_orders.append(
                    self.get_raw_list().pop(0)
                )
            else:
                break
        return due_orders

    def tst_random_add_order(self, time):
        rng = np.random.default_rng()

        quantity = rng.random(10)
        due_time = rng.random(10)

        quantity *= 10
        quantity += 1
        quantity = quantity.astype(int)

        due_time *= time
        due_time = due_time.astype(int)

        names = ["Motor", "Frame"]
        for q, d in zip(quantity, due_time):
            n = random.choice(names)
            o = Order(name=n, quantity=q, due_time=d)
            self.add_order_obj(o)

    def get_env_status(self):
        rst = defaultdict(list)
        for o in self.get_raw_list():
            o: Order
            rst["name"].append(o.name)
            rst["quantity"].append(o.quantity)
            rst["due_time"].append(o.due_time)
        return rst


if __name__ == '__main__':
    pass
