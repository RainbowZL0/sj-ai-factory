import bisect
import random

import numpy as np

from pycode.data_class import Order


def get_runtime_order_obj_list(init_order_list) -> list:
    rst = [
        Order(**order_dict)
        for order_dict in init_order_list
    ]
    return sorted(rst)


class OrderSellResult:
    def __init__(
            self,
            name,
            price_sell,
            need_to_sell_quantity,
            sold_quantity,
            sold_money,
            penalty_money,
            result_money,
    ):
        self.name = name
        self.price_sell = price_sell
        self.need_to_sell_quantity = need_to_sell_quantity
        self.sold_quantity = sold_quantity
        self.sold_money = sold_money
        self.penalty_money = penalty_money
        self.result_money = result_money

    def print_info(self):
        print(
            f"order info:\n"
            f"name = {self.name}\n"
            f"price_sell = {self.price_sell}\n"
            f"need_to_sell_quantity = {self.need_to_sell_quantity}\n"
            f"sold_quantity = {self.sold_quantity}\n"
            f"sold_money = {self.sold_money}\n"
            f"penalty_money = {self.penalty_money}\n"
            f"result_money = {self.result_money}\n"
        )


class OrderSellResultManagerRuntime:
    def __init__(
            self,
    ):
        self.step_result = []
        self.total_result = []

    def calcu_step_money(self):
        rst = 0
        for stock_sell_result in self.step_result:
            rst += stock_sell_result.result_money
        return rst

    def finish_step(self):
        self.total_result.extend(self.step_result)
        self.step_result.clear()

    def append(self, stock_sell_result: OrderSellResult):
        self.step_result.append(stock_sell_result)


class OrderManagerRuntime:
    def __init__(self, init_order_list: list, manual_simulation_steps):
        self.runtime_order_obj_list = get_runtime_order_obj_list(init_order_list)
        # TODO
        self.tst_random_add_order(manual_simulation_steps=manual_simulation_steps)

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

    def tst_random_add_order(self, manual_simulation_steps):
        rng = np.random.default_rng()

        quantity = rng.random(50)
        due_time = rng.random(50)

        quantity *= 10
        quantity += 1
        quantity = quantity.astype(int)

        due_time *= manual_simulation_steps
        due_time = due_time.astype(int)

        names = ["Motor", "Frame"]
        for q, d in zip(quantity, due_time):
            n = random.choice(names)
            o = Order(name=n, quantity=q, due_time=d)
            self.add_order_obj(o)

    def get_env_status(self):
        rst = {
            "order_name": [],
            "order_quantity": [],
            "order_due_time": [],
        }

        for o in self.get_raw_list():
            o: Order
            rst["order_name"].append(o.name)
            rst["order_quantity"].append(o.quantity)
            rst["order_due_time"].append(o.due_time)
        return rst


if __name__ == '__main__':
    pass
