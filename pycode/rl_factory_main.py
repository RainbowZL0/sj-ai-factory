"""
second_stage.py  --  discrete-time simulator for the minimal smart-factory

Run directly:
    python second_stage.py
Adjust DEVICE_SPEC / RECIPE_SPEC / DEMAND / SIM_TIME as needed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict

from pycode.CFG import DEVICE_SPEC
from pycode.data_class import Device, Recipe
from pycode.make_plot import draw_topology, plot_dashboard, plot_gantt

DEVICES = {d["id"]: Device(**d) for d in DEVICE_SPEC}

# very rough/fictional recipes
RECIPE_SPEC = [
    # T1
    Recipe(
        name="Cast_Iron", device_id="CASTER-01", cycle_time=60, power_kw=45.0,
        inputs={"IronOre": 30}, outputs={"IronIngot": 30},
    ),
    Recipe(
        name="Cast_Steel", device_id="CASTER-02", cycle_time=60, power_kw=50.0,
        inputs={"IronOre": 45, "Coal": 45}, outputs={"SteelIngot": 45}
    ),
    Recipe(
        name="Cast_Copper", device_id="CASTER-03", cycle_time=60, power_kw=50.0,
        inputs={"IronOre": 30, "Coal": 30}, outputs={"CopperIngot": 30}
    ),
    # T2
    Recipe(
        name="Ingot->Bar", device_id="CONSTRUCTOR-01", cycle_time=60, power_kw=15.0,
        inputs={"IronIngot": 15}, outputs={"IronBar": 15}
    ),
    Recipe(
        "Ingot->Screw", "CONSTRUCTOR-02", cycle_time=12, power_kw=12.0,
        inputs={"IronIngot": 12.5}, outputs={"Screw": 50}
    ),
    Recipe(
        "RotorAsm", "ASSEMBLER-01", cycle_time=20, power_kw=20.0,
        inputs={"IronBar": 4, "Screw": 100},
        outputs={"Rotor": 1}
    ),
    Recipe(
        "MotorFinal", "MANUFACTURER-01", 25, 30.0,
        inputs={"Rotor": 2},
        outputs={"Motor": 1}
    ),
]

RECIPES_BY_DEVICE: Dict[str, Recipe] = {
    r.device_id: r
    for r in RECIPE_SPEC
}


# --------------------------------------------------------------------------- #
# 2.  Simulator core                                                          #
# --------------------------------------------------------------------------- #

class DevState(Enum):
    IDLE = auto()
    RUNNING = auto()
    FINISHED = auto()


@dataclass
class DevRuntime:
    spec: Device
    recipe: Recipe
    state: DevState = DevState.IDLE
    t_left: int = 0  # seconds remaining for current batch

    def can_start(self, stock: Dict[str, int]) -> bool:
        """Check if enough inputs exist to launch a batch."""
        return all(stock[m] >= q for m, q in self.recipe.inputs.items())

    def start_batch(self, stock: Dict[str, int]):
        # 开始一次生产
        for m, q in self.recipe.inputs.items():
            stock[m] -= q
        self.state = DevState.RUNNING
        self.t_left = self.recipe.cycle_time

    def tick(self, stock: Dict[str, int]):
        if self.state is DevState.RUNNING:
            self.t_left -= 1
            if self.t_left == 0:
                # finish outputs
                for m, q in self.recipe.outputs.items():
                    stock[m] += q
                self.state = DevState.FINISHED
        elif self.state is DevState.FINISHED:
            self.state = DevState.IDLE  # ready for next batch


class FactorySim:
    def __init__(self, dt: int = 1):
        self.dt = dt
        self.all_dev_runtime = {
            id_: DevRuntime(DEVICES[id_], RECIPES_BY_DEVICE[id_])
            for id_ in DEVICES if id_ in RECIPES_BY_DEVICE
        }
        self.stock = defaultdict(int)
        self.clock = 0
        self.energy_kwh_used = 0.0

        # 画图
        self.hist_time: list[int] = []
        self.hist_energy: list[float] = []
        self.hist_stock: dict[str, list[int]] = defaultdict(list)
        self.hist_state: dict[str, list[str]] = {id_: [] for id_ in self.all_dev_runtime}

        # 甘特图
        self.hist_recipe: dict[str, list[str | None]] = {id_: [] for id_ in self.all_dev_runtime}

    def get_devices_runtime(self):
        return {
            id_: DevRuntime(DEVICES[id_], RECIPES_BY_DEVICE[id_])
            for id_ in DEVICES if id_ in RECIPES_BY_DEVICE
        }

    # ----- external helpers ------------------------------------------------ --
    def add_stock(self, material: str, qty: int):
        self.stock[material] += qty

    # ----- main loop -------------------------------------------------------- --
    def next_step(self):
        # 1) scheduler: naive rule -- start any idle device that can run
        for rt in self.all_dev_runtime.values():
            if rt.state is DevState.IDLE and rt.can_start(self.stock):
                rt.start_batch(self.stock)

        # 2) tick all devices
        for rt in self.all_dev_runtime.values():
            if rt.state is DevState.RUNNING:
                self.energy_kwh_used += rt.recipe.power_kw * (self.dt / 3600)
            rt.tick(self.stock)

        self.clock += self.dt

        # 记录工厂在该时间步的状态，用于画图
        # ----------- 记录数据 -----------
        self.hist_time.append(self.clock)
        self.hist_energy.append(self.energy_kwh_used)
        for mat in ("IronOre", "Coal", "IronIngot",
                    "SteelIngot", "IronBar", "Screw",
                    "Rotor", "Motor"):
            self.hist_stock[mat].append(self.stock[mat])  # 默认为 0
        for id_, drv in self.all_dev_runtime.items():
            self.hist_state[id_].append(drv.state.name)
            # 甘特图用，如果正在跑则记 recipe 名，否则记 None
            self.hist_recipe[id_].append(drv.recipe.name if drv.state is DevState.RUNNING else None)

    # ----- reporting -------------------------------------------------------- --
    def snapshot(self) -> str:
        sums = ", ".join(f"{k}:{v}" for k, v in self.stock.items() if v)
        devs = ", ".join(f"{d.spec.id}:{d.state.name}" for d in self.all_dev_runtime.values())
        return (f"[t={self.clock:4}s] stock({sums}) | devs({devs}) | "
                f"energy={self.energy_kwh_used:,.2f} kWh")


def main_entry():
    # --------------------------------------------------------------------------- #
    # 3.  Quick-and-dirty demo run                                               #
    # --------------------------------------------------------------------------- #
    sim_time = 300  # seconds
    print_every = 10  # seconds

    sim = FactorySim()
    # preload some raw materials
    sim.add_stock("IronOre", 300)
    sim.add_stock("Coal", 150)
    sim.add_stock("IronBar", 40)
    sim.add_stock("Screw", 300)

    for _ in range(sim_time):
        sim.next_step()
        if sim.clock % print_every == 0:
            print(sim.snapshot())

    print("\n=== final summary ===")
    print(sim.snapshot())

    draw_topology(DEVICES)
    plot_dashboard(sim)
    plot_gantt(sim, recipe_spec=RECIPE_SPEC)


if __name__ == "__main__":
    main_entry()
