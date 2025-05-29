from black.trans import defaultdict

from pycode.OrderManagerRuntime import OrderManagerRuntime
from pycode.StockManagerRuntime import StockManagerRuntime
from pycode.data_class import Price, Order


class StockSellResult:
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


class StockSellResultManagerRuntime:
    def __init__(
            self,
            stock_sell_result_list
    ):
        self.stock_sell_result_list: list[StockSellResult] = stock_sell_result_list

    def calcu_total_money(self):
        rst = 0
        for stock_sell_result in self.stock_sell_result_list:
            rst += stock_sell_result.result_money
        return rst

    def clean(self):
        self.stock_sell_result_list.clear()

    def append(self, stock_sell_result: StockSellResult):
        self.stock_sell_result_list.append(stock_sell_result)


class PriceManagerRuntime:
    def __init__(self, init_price_name_and_spec_dict):
        self.runtime_price_name_and_obj_dict = {
            name: Price(**price_dict)
            for name, price_dict in init_price_name_and_spec_dict.items()
        }
        self.stock_sell_result_mng = StockSellResultManagerRuntime([])

    def get_obj_by_name(self, name):
        return self.runtime_price_name_and_obj_dict[name]

    def get_objs(self):
        return self.runtime_price_name_and_obj_dict.values()

    def get_price_sell(self, name):
        return self.get_obj_by_name(name).price_sell

    def get_price_buy(self, name):
        return self.get_obj_by_name(name).price_buy

    def set_price_sell(self, name, price_sell):
        self.get_obj_by_name(name).price_sell = price_sell

    def set_price_buy(self, name, price_buy):
        self.get_obj_by_name(name).price_buy = price_buy

    def get_storage_cost_per_time_unit(self, name):
        return self.get_obj_by_name(name).storage_cost_per_time_unit

    def get_step_storage_cost(self, stock_mng: StockManagerRuntime):
        """单步仓库花钱"""
        rst = 0.0
        for material_name, material_stock_obj in stock_mng.get_items():
            m_storage_cost_per_time_unit = self.get_storage_cost_per_time_unit(material_name)
            m_stock_quantity = material_stock_obj.quantity
            rst += m_storage_cost_per_time_unit * m_stock_quantity
        return rst

    def get_step_energy_cost(self, step_energy_kwh_used):
        return step_energy_kwh_used * self.get_price_buy("energy")

    def get_step_rent_cost(self):
        return self.get_price_buy("rent")

    def get_step_sell_money(
            self,
            stock_mng: StockManagerRuntime,
            order_mng: OrderManagerRuntime
    ):
        self.stock_sell_result_mng.clean()
        order_mng.tick_due_time()
        due_order_list = order_mng.pop_due_orders()

        for o in due_order_list:
            o: Order
            name = o.name
            need_to_sell_quantity = o.quantity

            sold_quantity = stock_mng.try_remove_stock(
                name,
                need_to_sell_quantity,
            )
            sold_money = self.get_price_sell(name) * sold_quantity

            penalty_money = 0
            if sold_quantity < need_to_sell_quantity:
                quantity_diff = need_to_sell_quantity - sold_quantity
                penalty_money = calcu_sell_penalty_money(
                    name=name,
                    quantity_diff=quantity_diff
                )
            total_money = sold_money - penalty_money

            self.stock_sell_result_mng.append(
                StockSellResult(
                    name=name,
                    price_sell=sold_quantity,
                    need_to_sell_quantity=need_to_sell_quantity,
                    sold_quantity=sold_quantity,
                    sold_money=sold_money,
                    penalty_money=penalty_money,
                    result_money=total_money,
                )
            )
        return self.stock_sell_result_mng.calcu_total_money()

    def get_buy_material_cost(self):
        """暂时不考虑实现，材料免费"""
        # TODO
        return

    def get_env_status(self):
        rst = defaultdict(list)

        for o in self.get_objs():
            o: Price
            rst["name"].append(o.name)
            rst["price_buy"].append(o.price_buy)
            rst["price_sell"].append(o.price_sell)
            rst["storage_cost_per_time_unit"].append(o.storage_cost_per_time_unit)

        return rst


def calcu_sell_penalty_money(name, quantity_diff):
    """违约惩罚算法"""
    return 0
