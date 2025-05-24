from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pycode.data_class import Device, Recipe
from pycode.dev_runtime import DevState
from pycode.utils import (
    build_dict_of_dev_id_and_dev_runtime_obj,
    build_dict_of_dev_category_and_rcp_name,
)


class FactorySim:
    def __init__(
            self,
            device_id_and_spec_dict,
            recipe_name_and_spec_dict,
            init_runtime_device_id_and_rcp_name_dict,
            schedule_mode: Literal["greedy"],
            dt=1,
    ):
        """
        :param device_id_and_spec_dict:
        :param recipe_name_and_spec_dict:
        :param init_runtime_device_id_and_rcp_name_dict:
        :param dt: delta time
        :param schedule_mode: 是否以调度方式启动。无调度意味着只要原料足够就开机运转。
        """
        """复制传入参数为属性"""
        # self.device_id_and_spec_dict = device_id_and_spec_dict
        # self.recipe_name_and_spec_dict = recipe_name_and_spec_dict
        self.runtime_device_id_and_rcp_name_dict = init_runtime_device_id_and_rcp_name_dict
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
        # 字典，设备id -> Runtime
        self.dev_id_and_runtime_dict = build_dict_of_dev_id_and_dev_runtime_obj(
            device_id_and_obj_dict=self.device_id_and_obj_dict,
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
            runtime_device_id_and_rcp_name_dict=init_runtime_device_id_and_rcp_name_dict,
        )
        # 字典，设备类别名 -> 能做哪些配方名的list
        self.dev_category_and_rcp_name_dict = build_dict_of_dev_category_and_rcp_name(
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
        )

        self.stock = defaultdict(float)
        self.clock = 0
        self.energy_kwh_used = 0.0

        """画图"""
        self.hist_time: list[int] = []
        self.hist_energy: list[float] = []
        self.hist_stock: dict[str, list[float]] = defaultdict(list)
        self.hist_state: dict[str, list[str]] = {id_: [] for id_ in self.dev_id_and_runtime_dict}

        """甘特图"""
        self.hist_recipe: dict[str, list[str | None]] = {id_: [] for id_ in self.dev_id_and_runtime_dict}

    def apply_actions(self, action_dict: dict[str, str | None]):
        """
        action_dict: {device_id: recipe_name 或 'OFF' 或 None}, None表示这台机器维持原先的调度不作调整, 'OFF'关机
        只有当设备处于 IDLE 且 action 指定了合法配方，才切换它的 recipe 属性。
        """
        for dev_id, act in action_dict.items():
            rt = self.dev_id_and_runtime_dict.get(dev_id)
            if (
                    rt is None
                    or act is None
                    or rt.state is not DevState.IDLE  # TODO 不能只在IDLE状态才允许调度
            ):
                continue
            if act == "OFF":
                # 保持空闲，不启动
                continue
            # 验证这台设备类别允许做该配方
            cat = rt.device.category
            if act not in self.dev_category_and_rcp_name_dict[cat]:
                raise ValueError(f"{dev_id}({cat}) 不支持配方 {act}")
            # 切到新配方
            rt.recipe = self.recipe_name_and_obj_dict[act]

    # ----- external helpers ------------------------------------------------ --
    def add_stock(self, material: str, qty: int):
        self.stock[material] += qty

    def do_schedule(self, action_dict: dict | None):
        """决定本次step的所有设备的状态"""
        if self.schedule_mode == "greedy":
            for rt in self.dev_id_and_runtime_dict.values():
                if rt.state is DevState.IDLE and rt.can_start(self.stock):
                    rt.start_batch(self.stock)
        else:
            self.apply_actions(action_dict)

    # ----- main loop -------------------------------------------------------- --
    def run_for_this_step(self):
        # 2) tick all devices，用 dt 推进
        for rt in self.dev_id_and_runtime_dict.values():
            if rt.state is DevState.RUNNING:
                # 本步消耗 = 功率(kW)×(dt秒 ÷ 3600秒/时)
                self.energy_kwh_used += rt.recipe.power_kw * (self.dt / 3600)
            rt.tick(self.stock, self.dt)

        # 全局时钟也推进 dt
        self.clock += self.dt

        # 记录工厂在该时间步的状态，用于画图
        # ----------- 记录数据 -----------
        self.hist_time.append(self.clock)
        self.hist_energy.append(self.energy_kwh_used)
        for mat in ("IronOre", "Coal", "IronIngot",
                    "SteelIngot", "IronBar", "Screw",
                    "Rotor", "Motor"):
            self.hist_stock[mat].append(self.stock[mat])  # 默认为 0
        for dev_id, dev_runtime in self.dev_id_and_runtime_dict.items():
            self.hist_state[dev_id].append(dev_runtime.state.name)
            # 甘特图用，如果正在跑则记 recipe 名，否则记 None
            self.hist_recipe[dev_id].append(dev_runtime.recipe.name if dev_runtime.state is DevState.RUNNING else None)

    # ----- reporting -------------------------------------------------------- --
    def snapshot(self) -> str:
        sums = ", ".join(f"{k}:{v}" for k, v in self.stock.items() if v)
        devs = ", ".join(
            f"{runtime_i.device.id}:{runtime_i.state.name}" for runtime_i in self.dev_id_and_runtime_dict.values())
        return (f"[t={self.clock:4}s] stock({sums}) | devs({devs}) | "
                f"energy={self.energy_kwh_used:,.2f} kWh")

    def do_schedule_and_run_for_this_step(self, action_dict: dict | None):
        self.do_schedule(action_dict=action_dict)
        self.run_for_this_step()
