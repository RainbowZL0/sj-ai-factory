from __future__ import annotations

from black.trans import defaultdict

from pycode.OrderManagerRuntime import OrderManagerRuntime
from pycode.PriceManagerRuntime import PriceManagerRuntime
from pycode.Scheduler import Scheduler
from pycode.StockManagerRuntime import StockManagerRuntime
from pycode.dev_runtime import DevState, DevRuntime
from pycode.history_recorder import HistoryRecorder
from pycode.utils import (
    build_dict_of_dev_id_and_dev_runtime_obj,
)


class FactorySim:
    def __init__(
            self,
            device_id_and_obj_dict,
            recipe_name_and_obj_dict,
            init_stock_name_and_spec_dict,
            init_bind_of_device_id_and_rcp_name_dict,
            init_price_name_and_spec_dict,
            init_order_list,
            init_money,
            dt=1,
    ):
        """复制传入参数为属性"""
        self.dt = dt

        """新属性"""
        # 字典，设备id -> Runtime obj
        self.dev_id_and_dev_runtime_dict = build_dict_of_dev_id_and_dev_runtime_obj(
            device_id_and_obj_dict=device_id_and_obj_dict,
            recipe_name_and_obj_dict=recipe_name_and_obj_dict,
            runtime_device_id_and_rcp_name_dict=init_bind_of_device_id_and_rcp_name_dict,
        )

        # 运行时Stock管理器
        self.stock_mng = StockManagerRuntime(init_stock_name_and_spec_dict)
        # 运行时Price管理器
        self.price_mng = PriceManagerRuntime(init_price_name_and_spec_dict)
        # 运行时Order管理器
        self.order_mng = OrderManagerRuntime(init_order_list)

        self.clock = 0

        # 能耗
        self.total_energy_kwh_used = 0.0  # 累计
        self.step_energy_kwh_used = 0.0  # 单步
        # 余额
        self.total_balance = init_money
        self.step_balance = 0.0

        """历史记录管理器"""
        self.history_recorder = HistoryRecorder()

    def get_env_status(self):
        env_without_dev = {
            "total_energy": self.total_energy_kwh_used,
            "step_energy": self.step_energy_kwh_used,
            "total_balance": self.total_balance,
            "step_balance": self.step_balance,
            "clock": self.clock
        }

        dev_env = defaultdict(list)
        for dev_rt in self.dev_id_and_dev_runtime_dict.values():
            dev_rt: DevRuntime
            dev_env["dev_id"].append(dev_rt.device)
            dev_env["dev_state"].append(dev_rt.state)
            dev_env["dev_bind_recipe"].append(dev_rt.bind_recipe)

        return {**env_without_dev, **dev_env}

    def record_dev_status(self):
        h = self.history_recorder
        # 设备运行状态与甘特
        for dev_id, dev_rt in self.dev_id_and_dev_runtime_dict.items():
            h.log_vector("dev_state", dev_id, dev_rt.state.name)
            h.log_vector(
                "gantt",
                dev_id,
                dev_rt.bind_recipe.name
                if dev_rt.state is DevState.RUNNING
                else None
            )

    # ----- main loop -------------------------------------------------------- --

    def record_step_status_without_dev(self):
        h = self.history_recorder
        h.log_scalar("time", self.clock)
        h.log_scalar("total_energy", self.total_energy_kwh_used)
        h.log_scalar("total_balance", self.total_balance)
        h.log_scalar("step_balance", self.step_balance)

        # 库存向量
        for name, stock_obj in self.stock_mng.get_items():
            h.log_vector("stock", name, stock_obj.quantity)

        h.next_step()

    def snapshot(self) -> str:
        # TODO
        time_log = f"Time: {self.clock}\n"
        # dev
        dev_log = (
            f""
            f""
        )
        # stock
        # price
        # order
        # energy
        # money
        sums = ", ".join(
            f"{k}:{material_obj.quantity}"
            for k, material_obj in self.stock_mng.get_items()
            if material_obj.quantity
        )
        devs = ", ".join(
            f"{runtime_i.device.id}:{runtime_i.state.name}"
            for runtime_i in self.dev_id_and_dev_runtime_dict.values()
        )
        return (f"[t={self.clock:4}s] stock({sums}) | devs({devs}) | "
                f"energy={self.total_energy_kwh_used:,.2f} kWh")

    # ----- reporting -------------------------------------------------------- --
    def run_one_step_after_schedule(self, scheduler: Scheduler):
        if self.clock == 59:
            pass

        for dev_id, dev_rt in self.dev_id_and_dev_runtime_dict.items():
            # 如果调度指示是配方，不是None，且现在状态是IDLE；则检查能否启动
            schedule_plan = scheduler.schedule_plan[dev_id]
            if (schedule_plan is not None
                    and dev_rt.state is DevState.IDLE):
                if dev_rt.check_if_material_enough_to_start_bind_recipe(self.stock_mng):
                    dev_rt.start_batch(self.stock_mng)

            elif schedule_plan is not None and dev_rt.state is DevState.RUNNING:
                raise ValueError("调度计划出错，正在运行的机器不能指定配方，只能调度None")

        # 记录本轮机器状态
        self.record_dev_status()

        # 计算本步耗电量
        self.step_energy_kwh_used = 0.0
        for dev_rt in self.dev_id_and_dev_runtime_dict.values():
            if dev_rt.state is DevState.RUNNING:
                # 本步消耗 = 功率(kW)×(dt秒 ÷ 3600秒/时)
                self.step_energy_kwh_used += dev_rt.bind_recipe.power_kw * (self.dt / 3600)

        # tick all devices，用 dt 推进
        for dev_rt in self.dev_id_and_dev_runtime_dict.values():
            dev_rt.tick(self.stock_mng, self.dt)

        # 总能耗累加
        self.total_energy_kwh_used += self.step_energy_kwh_used

    def check_out_money(self):
        # 计算电费
        step_energy_money_cost = self.price_mng.get_step_energy_cost(
            step_energy_kwh_used=self.step_energy_kwh_used
        )
        # 计算出售
        step_sell_money = self.price_mng.get_step_sell_money(
            stock_mng=self.stock_mng,
            order_mng=self.order_mng,
        )
        # 计算库存费
        step_storage_cost = self.price_mng.get_step_storage_cost(self.stock_mng)
        # 计算租金
        step_rent_cost = self.price_mng.get_step_rent_cost()

        # 单步总金额变化
        self.step_balance = sum([
            -step_energy_money_cost,
            step_sell_money,
            -step_storage_cost,
            -step_rent_cost,
        ])
        # 所有步累计余额变化
        self.total_balance += self.step_balance

    def high_level_step(self, scheduler: Scheduler):
        # self.scheduler.apply_plan_to_runtime(
        #     dev_id_and_dev_runtime_dict=self.dev_id_and_dev_runtime_dict,
        #     recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
        # )
        self.run_one_step_after_schedule(scheduler)
        self.check_out_money()
        self.record_step_status_without_dev()
        # 全局时钟推进
        self.clock += self.dt
        pass
