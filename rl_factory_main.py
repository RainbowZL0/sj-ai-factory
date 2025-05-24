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
from typing import Dict, List

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx


# --------------------------------------------------------------------------- #
# 1.  Static hardware & recipe definition                                     #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Device:
    id: str
    category: str
    in_ch: int
    out_ch: int
    upstream: List[str]
    downstream: List[str]


@dataclass(frozen=True)
class Recipe:
    name: str
    device_id: str  # which device executes it
    cycle_time: int  # seconds per batch
    power_kw: float
    inputs: Dict[str, float]  # material → quantity / batch
    outputs: Dict[str, float]


# 铸造器 caster
# 构造器 constructor
# 组装器 assembler
# 产品制造器 manufacturer
DEVICE_SPEC = [
    # 没有固定上游（[]），意味着它直接吃外部原料。产物送往构造器。
    {
        "id": "CASTER-00",
        "category": "caster",  # 铸造器
        "in_ch": 1,
        "out_ch": 1,
        "upstream": [],
        "downstream": ["CONSTRUCTOR-01"],
    },
    {
        "id": "CASTER-01",
        "category": "caster",  # 铸造器
        "in_ch": 1,
        "out_ch": 1,
        "upstream": [],
        "downstream": ["CONSTRUCTOR-02"],
    },
    {
        "id": "CASTER-02",
        "category": "caster",  # 铸造器
        "in_ch": 2,
        "out_ch": 1,
        "upstream": [],
        "downstream": ["CONSTRUCTOR-03"],
    },
    {
        "id": "CASTER-03",
        "category": "caster",  # 铸造器
        "in_ch": 1,
        "out_ch": 1,
        "upstream": [],
        "downstream": ["CONSTRUCTOR-04"],  # 空闲
    },
    {
        "id": "CONSTRUCTOR-01",
        "category": "constructor",
        "in_ch": 1,
        "out_ch": 1,
        "upstream": ["CASTER-01"],
        "downstream": ["ASSEMBLER-01"],
    },
    {
        "id": "CONSTRUCTOR-02",
        "category": "constructor",
        "in_ch": 1,
        "out_ch": 1,
        "upstream": ["CASTER-02"],
        "downstream": ["ASSEMBLER-01"],
    },
    {
        "id": "CONSTRUCTOR-03",
        "category": "constructor",
        "in_ch": 1,
        "out_ch": 1,
        "upstream": ["CASTER-02"],
        "downstream": ["ASSEMBLER-02"],
    },
    {
        "id": "CONSTRUCTOR-04",
        "category": "constructor",
        "in_ch": 1,
        "out_ch": 1,
        "upstream": ["CASTER-02"],
        "downstream": ["ASSEMBLER-02"],
    },
    {
        "id": "ASSEMBLER-01",
        "category": "assembler",  # 组装器
        "in_ch": 2,
        "out_ch": 1,
        "upstream": ["CONSTRUCTOR-01", "CONSTRUCTOR-02"],
        "downstream": ["MANUFACTURER-01"],
    },
    {
        "id": "ASSEMBLER-02",
        "category": "assembler",  # 组装器
        "in_ch": 2,
        "out_ch": 1,
        "upstream": ["CONSTRUCTOR-01", "CONSTRUCTOR-02"],
        "downstream": ["MANUFACTURER-01"],
    },
    {
        "id": "MANUFACTURER-01",
        "category": "manufacturer",  # 产品制造器
        "in_ch": 2,
        "out_ch": 1,
        "upstream": ["ASSEMBLER-01"],
        "downstream": [],
    },
]

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

RECIPES_BY_DEVICE: Dict[str, Recipe] = {r.device_id: r for r in RECIPE_SPEC}


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
        self.devices = {
            id_: DevRuntime(DEVICES[id_], RECIPES_BY_DEVICE[id_])
            for id_ in DEVICES if id_ in RECIPES_BY_DEVICE
        }
        self.stock = defaultdict(int)
        self.clock = 0
        self.energy_kwh = 0.0

        # 画图
        self.hist_time: list[int] = []
        self.hist_energy: list[float] = []
        self.hist_stock: dict[str, list[int]] = defaultdict(list)
        self.hist_state: dict[str, list[str]] = {id_: [] for id_ in self.devices}

        # 甘特图
        self.hist_recipe: dict[str, list[str | None]] = {id_: [] for id_ in self.devices}

    def get_devices_runtime(self):
        return {
            id_: DevRuntime(DEVICES[id_], RECIPES_BY_DEVICE[id_])
            for id_ in DEVICES if id_ in RECIPES_BY_DEVICE
        }

    # ----- external helpers ------------------------------------------------ --
    def add_stock(self, material: str, qty: int):
        self.stock[material] += qty

    # ----- main loop -------------------------------------------------------- --
    def step(self):
        # 1) scheduler: naive rule -- start any idle device that can run
        for rt in self.devices.values():
            if rt.state is DevState.IDLE and rt.can_start(self.stock):
                rt.start_batch(self.stock)

        # 2) tick all devices
        for rt in self.devices.values():
            if rt.state is DevState.RUNNING:
                self.energy_kwh += rt.recipe.power_kw * (self.dt / 3600)
            rt.tick(self.stock)

        self.clock += self.dt

        # 记录工厂在该时间步的状态，用于画图
        # ----------- 记录数据 -----------
        self.hist_time.append(self.clock)
        self.hist_energy.append(self.energy_kwh)
        for mat in ("IronOre", "Coal", "IronIngot",
                    "SteelIngot", "IronBar", "Screw",
                    "Rotor", "Motor"):
            self.hist_stock[mat].append(self.stock[mat])  # 默认为 0
        for id_, drv in self.devices.items():
            self.hist_state[id_].append(drv.state.name)
            # 甘特图用，如果正在跑则记 recipe 名，否则记 None
            self.hist_recipe[id_].append(drv.recipe.name if drv.state is DevState.RUNNING else None)

    # ----- reporting -------------------------------------------------------- --
    def snapshot(self) -> str:
        sums = ", ".join(f"{k}:{v}" for k, v in self.stock.items() if v)
        devs = ", ".join(f"{d.spec.id}:{d.state.name}" for d in self.devices.values())
        return (f"[t={self.clock:4}s] stock({sums}) | devs({devs}) | "
                f"energy={self.energy_kwh:,.2f} kWh")


def plot_dashboard(sim: FactorySim) -> None:
    t = sim.hist_time
    fig, axs = plt.subplots(3, 1, figsize=(11, 9),
                            sharex=True, constrained_layout=True)

    # ① 原料 / 半成品 库存曲线
    for mat, series in sim.hist_stock.items():
        if any(series):  # 只画非空曲线
            axs[0].plot(t, series, label=mat)
    axs[0].set_ylabel("Inventory")
    axs[0].legend(loc="upper right")

    # ② 设备状态甘特图（简化版）
    state_code = {"IDLE": 0, "RUNNING": 1, "FINISHED": 2}
    y_offset = 0
    for dev_id, series in sim.hist_state.items():
        y_vals = [state_code[s] + y_offset for s in series]
        axs[1].step(t, y_vals, where="post", linewidth=2)
        y_offset += 3
    axs[1].set_yticks([1 + 3 * i for i in range(len(sim.hist_state))])
    axs[1].set_yticklabels(sim.hist_state.keys())
    axs[1].set_ylabel("Device State (idle/run/fin)")

    # ③ 累计耗电
    axs[2].plot(t, sim.hist_energy)
    axs[2].set_ylabel("kWh used")
    axs[2].set_xlabel("Time (s)")

    plt.show()
    save_path = "status_dashboard.png"
    fig.savefig(save_path, dpi=150)
    print(f"status_dashboard image saved to {save_path}")


# def draw_topology(devices: dict[str, Device],
#                   save_path: str = "device_topology.png") -> None:
#     graph = nx.DiGraph()
#     for dev in devices.values():
#         graph.add_node(dev.id, category=dev.category)
#         for dst in dev.downstream:
#             if dst:  # 防止空列表
#                 graph.add_edge(dev.id, dst)
#
#     pos = nx.spring_layout(graph, seed=42)
#     fig = plt.figure(figsize=(8, 5))
#     nx.draw_networkx_nodes(graph, pos, node_size=900, node_color="lightblue")
#     nx.draw_networkx_edges(graph, pos, arrowstyle="-|>", arrowsize=14)
#     nx.draw_networkx_labels(graph, pos, font_size=10)
#     plt.title("Factory Device Topology")
#     plt.axis("off")
#     plt.tight_layout()
#     fig.savefig(save_path, dpi=150)
#     print(f"Topology image saved to {save_path}")


def draw_topology(
        devices: dict[str, Device],
        save_path: str = "device_topology.png"
) -> None:
    """
    按 category 分列绘图：
        ┌───────────┐   ┌────────────┐   ┌────────────┐
        │  caster   │ → │ constructor│ → │  assembler │ …
    """

    # -------- 1. 建图 --------
    graph = nx.DiGraph()
    for dev in devices.values():
        dev: Device
        graph.add_node(dev.id, category=dev.category)
        for dst in dev.downstream:
            if dst:
                graph.add_edge(dev.id, dst)

    # -------- 2. 为每个类别分配一列 x 坐标 --------
    # 你可以手动写死列顺序，也可以自动根据出现顺序排序
    col_order = ["caster", "constructor", "assembler", "manufacturer"]
    x_of = {cat: i for i, cat in enumerate(col_order)}  # caster=0, constructor=1, ...

    # -------- 3. 同列内部，按节点名排序后均匀拉开 y --------
    pos: dict[str, tuple[float, float]] = {}
    for cat in col_order:
        nodes_in_cat = [d.id for d in devices.values() if d.category == cat]
        if not nodes_in_cat:
            continue
        nodes_in_cat.sort()  # 同列内部想用别的规则就改这里
        n = len(nodes_in_cat)
        y_coords = list(reversed(range(n)))  # n-1, n-2, … 0
        for y, node_id in zip(y_coords, nodes_in_cat):
            pos[node_id] = (x_of[cat], y)

    # -------- 4. 绘图 --------
    fig = plt.figure(figsize=(8, 4))
    nx.draw_networkx_nodes(graph, pos,
                           node_size=900,
                           node_color="lightblue",
                           edgecolors="k")
    nx.draw_networkx_edges(graph, pos,
                           arrowstyle="-|>",
                           arrowsize=14,
                           width=2)
    nx.draw_networkx_labels(graph, pos,
                            font_size=9)

    plt.title("Factory Device Topology (column-by-category)")
    plt.axis("off")
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    print(f"Topology image saved to {save_path}")


def plot_gantt(sim: FactorySim) -> None:
    """Draw a coloured-bar Gantt chart: each machine-row shows when it ran which recipe."""
    # ---------- colour dictionary ----------
    recipe_set = {r.name for r in RECIPE_SPEC}
    # cmap = plt.colormaps["tab20"].resampled(len(recipe_set))
    # cmap = cm.get_cmap("tab20", len(recipe_set))
    cmap = plt.colormaps.get_cmap("tab20").resampled(len(recipe_set))

    color_of = {name: cmap(i) for i, name in enumerate(sorted(recipe_set))}

    # ---------- time base ----------
    t_series = sim.hist_time
    dt = t_series[1] - t_series[0] if len(t_series) > 1 else 1

    # ---------- 只保留真正执行过作业的机器 ----------
    active_rows = [
        (dev_id, seq) for dev_id, seq in sim.hist_recipe.items()
        if any(r is not None for r in seq)
    ]
    n_rows = len(active_rows)

    # ---------- 画布尺寸随行数自动放大 ----------
    row_h = 0.8  # 单行高度（英寸）
    fig_height = 2 + n_rows * row_h  # 2 in 给标题+图例
    fig, ax = plt.subplots(figsize=(11, fig_height))

    # ---------- 主循环 ----------
    for y, (dev_id, rec_seq) in enumerate(active_rows):
        start, current = None, None
        for idx, rec in enumerate(rec_seq):
            if rec != current:
                if current is not None:  # 结束上一段
                    ax.broken_barh(
                        [(start * dt, (idx - start) * dt)],
                        (y - 0.4, 0.8),
                        facecolors=color_of[current],
                    )
                current, start = rec, idx
        if current is not None:  # 收尾
            ax.broken_barh(
                [(start * dt, (len(rec_seq) - start) * dt)],
                (y - 0.4, 0.8),
                facecolors=color_of[current],
            )
        # 行标签
        ax.text(-2, y, dev_id, va="center", ha="right")

    # ---------- 轴 & 图例 ----------
    ax.set_ylim(-0.5, n_rows - 0.5)
    ax.set_yticks([])  # y 轴刻度隐藏
    ax.set_xlabel("Time (s)")
    ax.set_title("Device–Recipe Gantt Chart")

    handles = [mpatches.Patch(color=clr, label=name) for name, clr in color_of.items()]
    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc="upper left")

    fig.subplots_adjust(left=0.18)  # 左边距给设备名
    plt.tight_layout()
    plt.show()
    save_path = "gantt.png"
    fig.savefig(save_path, dpi=150)
    print(f"Gantt image saved to {save_path}")


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
        sim.step()
        if sim.clock % print_every == 0:
            print(sim.snapshot())

    print("\n=== final summary ===")
    print(sim.snapshot())

    draw_topology(DEVICES)
    plot_dashboard(sim)
    plot_gantt(sim)


if __name__ == "__main__":
    main_entry()
