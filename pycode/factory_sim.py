from __future__ import annotations

from collections import defaultdict

from pycode.data_class import Device, Recipe
from pycode.dev_runtime import DevState
from pycode.utils import build_dict_of_dev_id_and_dev_runtime_obj


class FactorySim:
    def __init__(
            self,
            device_id_and_spec_dict,
            recipe_name_and_spec_dict,
            init_runtime_device_id_and_rcp_name_dict,
    ):
        """复制传入参数为属性"""
        self.device_id_and_spec_dict = device_id_and_spec_dict
        self.recipe_name_and_spec_dict = recipe_name_and_spec_dict
        self.runtime_device_id_and_rcp_name_dict = init_runtime_device_id_and_rcp_name_dict

        """新属性"""
        self.device_id_and_obj_dict = {
            dev_id: Device(**dev_dict)
            for dev_id, dev_dict in device_id_and_spec_dict.items()
        }
        self.recipe_name_and_obj_dict = {
            rcp_name: Recipe(**rcp_dict)
            for rcp_name, rcp_dict in recipe_name_and_spec_dict.items()
        }
        self.dev_id_and_runtime_dict = build_dict_of_dev_id_and_dev_runtime_obj(
            device_id_and_obj_dict=self.device_id_and_obj_dict,
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
            runtime_device_id_and_rcp_name_dict=self.runtime_device_id_and_rcp_name_dict,
        )

        self.stock = defaultdict(float)
        self.clock = 0
        self.energy_kwh_used = 0.0

        # 画图
        self.hist_time: list[int] = []
        self.hist_energy: list[float] = []
        self.hist_stock: dict[str, list[float]] = defaultdict(list)
        self.hist_state: dict[str, list[str]] = {id_: [] for id_ in self.dev_id_and_runtime_dict}

        # 甘特图
        self.hist_recipe: dict[str, list[str | None]] = {id_: [] for id_ in self.dev_id_and_runtime_dict}

    # ----- external helpers ------------------------------------------------ --
    def add_stock(self, material: str, qty: int):
        self.stock[material] += qty

    # ----- main loop -------------------------------------------------------- --
    def next_step(self):
        # 1) scheduler: naive rule -- start any idle device that can run
        for rt in self.dev_id_and_runtime_dict.values():
            if rt.state is DevState.IDLE and rt.can_start(self.stock):
                rt.start_batch(self.stock)

        # 2) tick all devices
        for rt in self.dev_id_and_runtime_dict.values():
            if rt.state is DevState.RUNNING:
                self.energy_kwh_used += rt.recipe.power_kw * (1 / 3600)
            rt.tick(self.stock)

        self.clock += 1

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
