"""Charts: status dashboard, Gantt chart, material flow. All are saved to files; no windows open."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402

from sjfactory.sim import STOP  # noqa: E402
from sjfactory.spec import Scenario  # noqa: E402

if TYPE_CHECKING:
    from sjfactory.recorder import Recorder


def _recipe_colors(scenario: Scenario):
    cmap = plt.colormaps["tab20"]
    return [cmap(i % 20) for i in range(len(scenario.recipes))]


def draw_dashboard(rec: Recorder, path: Path):
    sc = rec.scenario
    t = rec.time
    scalars = rec.scalars()
    stock = rec.stock_frame()
    running = rec.running_matrix()

    fig, axs = plt.subplots(5, 1, figsize=(11, 16), sharex=True)

    # 1. Stock: only materials that change, on a log scale so huge raw stocks don't flatten the rest
    for name in stock.columns:
        col = stock[name].to_numpy()
        if col.min() != col.max():
            axs[0].plot(t, col, label=name)
    axs[0].set_yscale("symlog")
    axs[0].set_ylabel("Stock")
    axs[0].legend(fontsize=8, ncol=2)

    # 2. How many machines of each category are running
    categories = sorted({m.category for m in sc.machines})
    for cat in categories:
        cols = [i for i, m in enumerate(sc.machines) if m.category == cat]
        axs[1].step(t, (running[:, cols] != STOP).sum(axis=1), where="post", label=cat)
    axs[1].set_ylabel("Machines running")
    axs[1].legend(fontsize=8)

    axs[2].plot(t, scalars["total_energy_kwh"])
    axs[2].set_ylabel("Energy (kWh)")

    axs[3].plot(t, scalars["cash"])
    axs[3].set_ylabel("Cash")

    axs[4].plot(t, scalars["cash_change"])
    axs[4].set_ylabel("Cash change per second")
    axs[4].set_xlabel("Time (s)")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def draw_gantt(rec: Recorder, path: Path):
    """One row per machine; colored bars show when it ran which recipe"""
    sc = rec.scenario
    running = rec.running_matrix()
    colors = _recipe_colors(sc)

    rows = [m for m in range(len(sc.machines)) if running.size and (running[:, m] != STOP).any()]
    fig, ax = plt.subplots(figsize=(12, 2 + 0.3 * len(rows)))

    for y, m in enumerate(rows):
        seq = running[:, m]
        # find stretches where the recipe stays the same
        edges = np.flatnonzero(np.diff(seq)) + 1
        starts = np.concatenate([[0], edges])
        ends = np.concatenate([edges, [len(seq)]])
        for a, b in zip(starts, ends):
            if seq[a] != STOP:
                ax.broken_barh([(a, b - a)], (y - 0.4, 0.8), facecolors=colors[seq[a]])

    ax.set_yticks(range(len(rows)), [sc.machines[m].id for m in rows], fontsize=8)
    ax.set_ylim(-0.5, len(rows) - 0.5)
    ax.invert_yaxis()
    ax.set_xlabel("Time (s)")
    ax.set_title("Machine schedule")
    used = sorted({int(r) for r in np.unique(running) if r != STOP})
    ax.legend(
        handles=[mpatches.Patch(color=colors[r], label=sc.recipes[r].name) for r in used],
        bbox_to_anchor=(1.01, 1),
        loc="upper left",
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def draw_material_flow(scenario: Scenario, path: Path):
    """Material -> recipe -> material flow chart. All machines share one warehouse, so this is how production really connects."""
    g = nx.DiGraph()
    for m in scenario.materials:
        g.add_node(m.name, kind="material")
    machine_count = {r.name: 0 for r in scenario.recipes}
    for m in scenario.machines:
        if m.initial_recipe:
            machine_count[m.initial_recipe] += 1
    for r in scenario.recipes:
        node = f"{r.name}\n{r.category} x{machine_count[r.name]}"
        g.add_node(node, kind="recipe")
        for name, q in r.inputs.items():
            g.add_edge(name, node, label=f"{q:g}")
        for name, q in r.outputs.items():
            g.add_edge(node, name, label=f"{q:g}")

    if nx.is_directed_acyclic_graph(g):
        for layer, nodes in enumerate(nx.topological_generations(g)):
            for n in nodes:
                g.nodes[n]["layer"] = layer
        pos = nx.multipartite_layout(g, subset_key="layer")
    else:
        pos = nx.spring_layout(g, seed=0)

    fig, ax = plt.subplots(figsize=(16, 10))
    materials = [n for n, d in g.nodes(data=True) if d["kind"] == "material"]
    recipes = [n for n, d in g.nodes(data=True) if d["kind"] == "recipe"]
    nx.draw_networkx_nodes(g, pos, nodelist=materials, node_color="lightblue", node_size=900, ax=ax)
    nx.draw_networkx_nodes(
        g, pos, nodelist=recipes, node_color="moccasin", node_shape="s", node_size=1600, ax=ax
    )
    nx.draw_networkx_edges(g, pos, arrowstyle="-|>", arrowsize=12, node_size=1400, ax=ax)
    nx.draw_networkx_edge_labels(g, pos, edge_labels=nx.get_edge_attributes(g, "label"), font_size=7, ax=ax)
    nx.draw_networkx_labels(g, pos, font_size=7, ax=ax)
    ax.set_title("Material flow (blue = material, orange = recipe; xN = machines starting on it)")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
