from __future__ import annotations

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx

from pycode.data_class import Device
from pycode.history_recorder import HistoryRecorder


def draw_dashboard(hr: HistoryRecorder):
    time_list = hr.get_scalar("time")
    fig, axs = plt.subplots(5, 1, figsize=(11, 16), sharex=True)

    # ① 库存
    for stock_name, list_of_quantity_by_time in hr.vector_logs["stock"].items():
        if any(list_of_quantity_by_time):
            axs[0].plot(time_list, list_of_quantity_by_time, label=stock_name)
    axs[0].set_ylabel("Inventory")
    axs[0].legend()

    # ② 设备状态
    state_code = {"IDLE": 0, "RUNNING": 1}
    offset = 0
    for dev_id, seq in hr.vector_logs["dev_state"].items():
        axs[1].step(
            time_list,
            [state_code[s] + offset for s in seq],
            where="post",
            label=dev_id,
        )
        offset += 3
    axs[1].set_ylabel("Dev state")
    # axs[1].legend()

    # ③ 能耗
    axs[2].plot(time_list, hr.get_scalar("total_energy"))
    axs[2].set_ylabel("kWh")

    # ④ 余额
    axs[3].plot(time_list, hr.get_scalar("total_balance"))
    axs[3].set_ylabel("Balance")

    # ⑤ 单步现金流
    axs[4].plot(time_list, hr.get_scalar("step_balance"))
    axs[4].set_ylabel("ΔCash")
    axs[4].set_xlabel("Time")

    plt.tight_layout()
    plt.show()

    save_path = "../pics/status_dashboard.png"
    fig.savefig(save_path, dpi=150)
    print(f"status_dashboard image saved to {save_path}")


def draw_device_topology(
        devices: dict[str, Device],
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
    col_order = ["Caster", "Constructor", "Assembler", "Manufacturer"]
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
    fig = plt.figure(figsize=(12, 12))
    nx.draw_networkx_nodes(graph, pos,
                           node_size=500,
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
    fig.show()
    plt.close()

    save_path = "../pics/device_topology.png"
    fig.savefig(save_path, dpi=150)
    print(f"Topology image saved to {save_path}")


def draw_gantt(hr: HistoryRecorder, recipe_obj_list) -> None:
    """Draw a coloured-bar Gantt chart: each machine-row shows when it ran which recipe."""
    # ---------- colour dictionary ----------
    recipe_set = {r.name for r in recipe_obj_list}
    cmap = plt.colormaps.get_cmap("tab20").resampled(len(recipe_set))

    color_of = {name: cmap(i) for i, name in enumerate(sorted(recipe_set))}

    # ---------- time base ----------
    t_series = hr.get_scalar("time")
    dt = t_series[1] - t_series[0] if len(t_series) > 1 else 1

    # ---------- 只保留真正执行过作业的机器 ----------
    active_rows = [
        (dev_id, seq) for dev_id, seq in hr.vector_logs["gantt"].items()
        if any(r is not None for r in seq)
    ]
    n_rows = len(active_rows)

    # ---------- 画布尺寸随行数自动放大 ----------
    row_h = 0.3  # 单行高度（英寸）
    fig_height = 2 + n_rows * row_h  # 2 in 给标题+图例
    fig, ax = plt.subplots(figsize=(12, fig_height))

    # ---------- 主循环 ----------
    for y, (dev_id, rec_seq) in enumerate(active_rows):
        start, current = None, None
        for idx, hr in enumerate(rec_seq):
            if hr != current:
                if current is not None:  # 结束上一段
                    ax.broken_barh(
                        [(start * dt, (idx - start) * dt)],
                        (y - 0.4, 0.8),
                        facecolors=color_of[current],
                    )
                current, start = hr, idx
        if current is not None:  # 收尾
            ax.broken_barh(
                [(start * dt, (len(rec_seq) - start) * dt)],
                (y - 0.4, 0.8),
                facecolors=color_of[current],
            )
        # 行标签
        ax.text(
            -20,
            y,
            dev_id,
            va="center",
            ha="right",
            clip_on=False
        )

    # ---------- 轴 & 图例 ----------
    ax.set_ylim(-0.5, n_rows - 0.5)
    ax.set_yticks([])  # y 轴刻度隐藏
    ax.set_xlabel("Time (s)")
    ax.set_title("Device–Recipe Gantt Chart")

    handles = [mpatches.Patch(color=clr, label=name) for name, clr in color_of.items()]
    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc="upper left")

    fig.subplots_adjust(left=0.3)  # 左边距给设备名
    plt.tight_layout()
    plt.show()
    save_path = "../pics/gantt.png"
    fig.savefig(save_path, dpi=150)
    print(f"Gantt image saved to {save_path}")
