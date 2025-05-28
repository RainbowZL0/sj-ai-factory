from __future__ import annotations

from typing import Literal

from pycode.OrderManagerRuntime import OrderManagerRuntime
from pycode.PriceManagerRuntime import PriceManagerRuntime
from pycode.StockManagerRuntime import StockManagerRuntime
from pycode.data_class import Device, Recipe
from pycode.dev_runtime import DevState
from pycode.history_recorder import HistoryRecorder
from pycode.utils import (
    build_dict_of_dev_id_and_dev_runtime_obj,
    build_dict_of_dev_category_and_rcp_name,
)


class FactorySim:
    def __init__(
            self,
            device_id_and_spec_dict,
            recipe_name_and_spec_dict,
            init_stock_name_and_spec_dict,
            init_bind_of_device_id_and_rcp_name_dict,
            init_price_name_and_spec_dict,
            init_order_list,
            init_money,
            schedule_mode: Literal["greedy", "manual"],
            dt=1,
    ):
        """
        :param device_id_and_spec_dict:
        :param recipe_name_and_spec_dict:
        :param init_bind_of_device_id_and_rcp_name_dict:
        :param dt: delta time
        :param schedule_mode: 是否以调度方式启动。无调度意味着只要原料足够就开机运转。
        """
        """复制传入参数为属性"""
        self.runtime_bind_of_device_id_and_rcp_name_dict = init_bind_of_device_id_and_rcp_name_dict
        self.schedule_mode = schedule_mode
        self.dt = dt

        """新属性"""
        # 字典，设备id -> 设备obj
        self.device_id_and_obj_dict = {
            dev_id: Device(**dev_dict)
            for dev_id, dev_dict in device_id_and_spec_dict.items()
        }
        # 字典，配方名 -> 配方obj
        self.recipe_name_and_obj_dict = {
            rcp_name: Recipe(**rcp_dict)
            for rcp_name, rcp_dict in recipe_name_and_spec_dict.items()
        }

        # 运行时Stock管理器
        self.stock_mng = StockManagerRuntime(init_stock_name_and_spec_dict)
        # 运行时Price管理器
        self.price_mng = PriceManagerRuntime(init_price_name_and_spec_dict)
        # 运行时Order管理器
        self.order_mng = OrderManagerRuntime(init_order_list)

        # 字典，设备id -> Runtime obj
        self.dev_id_and_dev_runtime_dict = build_dict_of_dev_id_and_dev_runtime_obj(
            device_id_and_obj_dict=self.device_id_and_obj_dict,
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
            runtime_device_id_and_rcp_name_dict=init_bind_of_device_id_and_rcp_name_dict,
        )
        # 字典，设备类别名 -> 能做哪些配方名的list
        self.dev_category_and_rcp_name_dict = build_dict_of_dev_category_and_rcp_name(
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
        )

        self.clock = 0

        # 能耗
        self.total_energy_kwh_used = 0.0  # 累计
        self.step_energy_kwh_used = 0.0  # 单步
        # 余额
        self.total_balance = init_money
        self.step_balance = 0.0

        """历史记录管理器"""
        self.history_recorder = HistoryRecorder()

    def apply_actions(self, action_dict: dict[str, str | None]):
        """
        action_dict: {device_id: recipe_name 或 'OFF' 或 None}, None表示这台机器维持原先的调度不作调整, 'OFF'关机
        只有当设备处于 IDLE 且 action 指定了合法配方，才切换它的 recipe 属性。
        """
        assert action_dict is not None
        for dev_id, act in action_dict.items():
            dev_rt = self.dev_id_and_dev_runtime_dict.get(dev_id)
            if (
                    dev_rt is None
                    or act is None
                    or act == "OFF"  # TODO 不能在关机时不能调度
                    or dev_rt.state is not DevState.IDLE  # TODO 不能只在IDLE状态才允许调度
            ):
                continue
            # 验证这台设备类别允许做该配方
            cat = dev_rt.device.category
            if act not in self.dev_category_and_rcp_name_dict[cat]:
                raise ValueError(f"{dev_id}({cat}) 不支持配方 {act}")
            # 切到新配方
            dev_rt.recipe = self.recipe_name_and_obj_dict[act]
            # TODO devruntime里的配方也要改

    def do_schedule(self, action_dict: dict | None):
        """决定本次step的所有设备的状态"""
        if self.schedule_mode == "greedy":
            pass
        else:
            self.apply_actions(action_dict)

    # ----- main loop -------------------------------------------------------- --
    def run_one_step_after_schedule(self):
        # 检查能启动的生产，并启动
        for dev_rt in self.dev_id_and_dev_runtime_dict.values():
            if dev_rt.can_start(self.stock_mng):
                dev_rt.start_batch(self.stock_mng)

        self.step_energy_kwh_used = 0.0
        # tick all devices，用 dt 推进
        for rt in self.dev_id_and_dev_runtime_dict.values():
            if rt.state is DevState.RUNNING:
                # 本步消耗 = 功率(kW)×(dt秒 ÷ 3600秒/时)
                self.step_energy_kwh_used += rt.recipe.power_kw * (self.dt / 3600)
            rt.tick(self.stock_mng, self.dt)
        # 全局时钟也推进 dt
        self.clock += self.dt
        # 总能耗累加
        self.total_energy_kwh_used += self.step_energy_kwh_used

        self.record_status()

    def record_status(self):
        h = self.history_recorder
        h.log_scalar("time", self.clock)
        h.log_scalar("total_energy", self.total_energy_kwh_used)
        h.log_scalar("total_balance", self.total_balance)
        h.log_scalar("step_balance", self.step_balance)

        # 库存向量
        for name, stock_obj in self.stock_mng.get_items():
            h.log_vector("stock", name, stock_obj.quantity)

        # 设备运行状态与甘特
        for dev_id, rt in self.dev_id_and_dev_runtime_dict.items():
            h.log_vector("dev_state", dev_id, rt.state.name)
            h.log_vector("gantt", dev_id,
                         rt.recipe.name if rt.state is DevState.RUNNING else None)

        h.next_step()

    # ----- reporting -------------------------------------------------------- --
    def snapshot(self) -> str:
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

    def do_schedule_and_run_for_this_step(self, action_dict: dict | None):
        self.do_schedule(action_dict=action_dict)
        self.run_one_step_after_schedule()
        self.check_out_money()
        pass
