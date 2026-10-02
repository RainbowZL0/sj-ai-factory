"""Web pages for looking at results. Open them in any browser; no server needed.

report.html    one episode: money, orders, machine schedule, stock, compared with the fixed rules
training.html  training progress; reloads itself every few seconds while training runs
index.html     every run in runs/, so you can see whether a code change helped

Charts are interactive (Plotly): hover for exact values, drag to zoom, double-click to reset.
The Plotly script is saved once next to the run folders (plotly.min.js), so pages work offline.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from sjfactory.sim import STOP

if TYPE_CHECKING:
    from sjfactory.recorder import Recorder

# Colors. Categorical slots are used in this fixed order; each color always means the same thing on a page.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
POLICY_COLOR = {"model": SERIES[0], "keep": SERIES[1], "random": SERIES[2]}
POLICY_LABEL = {"model": "Trained model", "keep": "Keep (fixed rule)", "random": "Random"}
# The two ways a trained model is tested; same color (it is the same model), told apart by line style
MODE_DASH = {"fixed": "solid", "sampled": "dash"}
MODE_LABEL = {"fixed": "no randomness", "sampled": "with randomness"}
MONEY_COLOR = {"revenue": SERIES[5], "costs": SERIES[6], "penalty": SERIES[7]}
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SURFACE, PAGE = "#fcfcfb", "#f9f9f7"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

REFRESH_SECONDS = 15

CSS = f"""
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: {PAGE}; color: {INK}; font-family: {FONT}; font-size: 14px; }}
main {{ max-width: 1280px; margin: 0 auto; padding: 24px 24px 64px; }}
header h1 {{ font-size: 22px; margin: 0 0 4px; }}
header .meta {{ color: {INK2}; }}
header nav a {{ margin-right: 16px; }}
a {{ color: #256abf; }}
.badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; margin-left: 8px; vertical-align: middle; }}
.badge.live {{ background: #fff3d6; color: #7a5200; }}
.badge.done {{ background: #e3f4e3; color: #006300; }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 20px 0; }}
.tile {{ background: {SURFACE}; border: 1px solid rgba(11,11,11,0.10); border-radius: 10px; padding: 14px 16px; }}
.tile .label {{ color: {INK2}; font-size: 12px; }}
.tile .value {{ font-size: 26px; font-weight: 600; margin-top: 4px; }}
.tile .sub {{ color: {INK2}; font-size: 12px; margin-top: 4px; }}
.up {{ color: #006300; font-weight: 600; }}
.down {{ color: {CRITICAL}; font-weight: 600; }}
section {{ background: {SURFACE}; border: 1px solid rgba(11,11,11,0.10); border-radius: 10px; padding: 16px 16px 8px; margin: 16px 0; }}
section h2 {{ font-size: 16px; margin: 0 0 2px; }}
section p.how {{ color: {INK2}; margin: 0 0 8px; font-size: 13px; }}
.grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; }}
.grid2 section {{ margin: 0; min-width: 0; overflow: hidden; }}
table {{ border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid {GRID}; }}
th {{ color: {INK2}; font-weight: 600; font-size: 12px; }}
td.num, th.num {{ text-align: right; }}
img {{ max-width: 100%; }}
details summary {{ cursor: pointer; color: {INK2}; }}
"""


# Building blocks


def _ensure_plotly(folder: Path):
    path = folder / "plotly.min.js"
    if not path.exists():
        from plotly.offline import get_plotlyjs

        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(get_plotlyjs(), encoding="utf-8")


def _page(title: str, body: str, plotly_src: str, refresh: int | None = None) -> str:
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">{meta}
<title>{html.escape(title)}</title>
<style>{CSS}</style>
<script src="{plotly_src}"></script>
</head><body><main>
{body}
</main>
<script>
// Charts are drawn while the page is still laying out; fit them to their final card size
window.addEventListener("load", () =>
  document.querySelectorAll(".js-plotly-plot").forEach((el) => Plotly.Plots.resize(el)));
</script>
</body></html>
"""


def _style(fig: go.Figure, height=320, xtitle=None, ytitle=None, hover="x unified") -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=64, r=24, t=36, b=44),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=12, color=INK2),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, bgcolor="rgba(0,0,0,0)"),
        autosize=True,
        hovermode=hover,
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=AXIS),
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, ticks="outside", tickcolor=AXIS, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickformat=",~r")
    if xtitle:
        fig.update_xaxes(title_text=xtitle)
    if ytitle:
        fig.update_yaxes(title_text=ytitle)
    return fig


def _chart(fig: go.Figure) -> str:
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displaylogo": False, "responsive": True},
    )


def _section(title: str, how: str, content: str) -> str:
    return f'<section><h2>{html.escape(title)}</h2><p class="how">{how}</p>{content}</section>'


def _tile(label: str, value: str, sub: str = "") -> str:
    return (
        f'<div class="tile"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{value}</div><div class="sub">{sub}</div></div>'
    )


def _money(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x:,.0f}"


def _pct(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{100 * x:.0f}%"


def _delta(x, ref, what="") -> str:
    """'▲ 1,200 more than keep' in green, or '▼ ...' in red. The arrow and word carry the meaning, not only the color."""
    if ref is None or x is None:
        return ""
    d = x - ref
    if abs(d) < 0.5:
        return f"same as {what}"
    cls, arrow, word = ("up", "▲", "more") if d > 0 else ("down", "▼", "less")
    return f'<span class="{cls}">{arrow} {abs(d):,.0f}</span> {word} than {what}'


def _read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_config(out: Path, **fields):
    (out / "config.json").write_text(json.dumps(fields, indent=2, default=str), encoding="utf-8")


# Episode report


def _cash_figure(curves: dict[str, dict], initial_cash: float) -> go.Figure:
    fig = go.Figure()
    for name, c in curves.items():
        policy, _, mode = name.partition(":")
        fig.add_scatter(
            x=c["time"],
            y=c["cash"],
            name=POLICY_LABEL.get(policy, policy) + (f" ({MODE_LABEL[mode]})" if mode else ""),
            line=dict(color=POLICY_COLOR.get(policy, MUTED), width=2, dash=MODE_DASH.get(mode, "solid")),
            hovertemplate="%{y:,.0f}",
        )
    fig.add_hline(y=initial_cash, line=dict(color=AXIS, width=1))
    return _style(fig, 340, "Time (s)", "Cash")


def _money_figure(rec: Recorder) -> go.Figure:
    s = rec.scalars()
    t = s["time"]
    costs = (s["energy_cost"] + s["storage_cost"] + s["rent"]).cumsum()
    fig = go.Figure()
    for key, y, label in [
        ("revenue", s["revenue"].cumsum(), "Revenue"),
        ("costs", costs, "Running costs"),
        ("penalty", s["penalty"].cumsum(), "Penalties"),
    ]:
        fig.add_scatter(
            x=t, y=y, name=label, line=dict(color=MONEY_COLOR[key], width=2), hovertemplate="%{y:,.0f}"
        )
    return _style(fig, 300, "Time (s)", "Total so far")


def _orders_figure(rec: Recorder) -> go.Figure:
    d = rec.deliveries_frame()
    fig = go.Figure()
    if d.empty:
        return _style(fig, 200)
    share = np.where(d["ordered"] > 0, d["shipped"] / d["ordered"].where(d["ordered"] > 0, 1), 1.0)
    status = np.select([share >= 1, share <= 0], ["Filled", "Missed"], "Partly filled")
    style = {
        "Filled": (GOOD, "circle"),
        "Partly filled": (WARNING, "diamond"),
        "Missed": (CRITICAL, "x"),
    }
    for name, (color, symbol) in style.items():
        part = d[status == name]
        if part.empty:
            continue
        fig.add_scatter(
            x=part["time"],
            y=part["product"],
            mode="markers",
            name=f"{name} ({len(part)})",
            marker=dict(
                color=color,
                symbol=symbol,
                size=8 + 1.6 * part["ordered"],
                line=dict(color=SURFACE, width=2),
            ),
            customdata=part[["ordered", "shipped", "revenue", "penalty"]].to_numpy(),
            hovertemplate=(
                "%{y} due at %{x} s<br>ordered %{customdata[0]:.0f}, shipped %{customdata[1]:.0f}"
                "<br>revenue %{customdata[2]:,.0f}, penalty %{customdata[3]:,.0f}<extra></extra>"
            ),
        )
    fig.update_yaxes(type="category")
    return _style(fig, 120 + 60 * d["product"].nunique(), "Due time (s)", None, hover="closest")


def _recipe_colors(scenario) -> dict[int, str]:
    """Each machine category gets its own slots in order, so a row never shows two recipes in one color"""
    colors = {}
    for cat in dict.fromkeys(m.category for m in scenario.machines):
        for slot, r in enumerate(scenario.recipes_for(cat)):
            colors[r] = SERIES[slot] if slot < len(SERIES) else MUTED
    return colors


def _gantt_figure(rec: Recorder) -> go.Figure:
    sc = rec.scenario
    running = rec.running_matrix()
    colors = _recipe_colors(sc)
    ids = [m.id for m in sc.machines]
    bars: dict[int, dict[str, list]] = {}
    for m, mid in enumerate(ids):
        seq = running[:, m] if running.size else np.array([], dtype=int)
        if not len(seq):
            continue
        edges = np.flatnonzero(np.diff(seq)) + 1
        for a, b in zip(np.r_[0, edges], np.r_[edges, len(seq)]):
            r = int(seq[a])
            if r == STOP:
                continue
            bar = bars.setdefault(r, {"y": [], "base": [], "x": []})
            bar["y"].append(mid)
            bar["base"].append(int(a))
            bar["x"].append(int(b - a))

    fig = go.Figure()
    for r in sorted(bars):
        rcp = sc.recipes[r]
        b = bars[r]
        fig.add_bar(
            y=b["y"],
            base=b["base"],
            x=b["x"],
            orientation="h",
            name=rcp.name,
            legendgroup=rcp.category,
            legendgrouptitle_text=rcp.category,
            marker=dict(color=colors[r], line=dict(width=0)),
            customdata=np.column_stack([b["base"], np.add(b["base"], b["x"])]),
            hovertemplate=f"%{{y}}: {rcp.name}<br>%{{customdata[0]}}–%{{customdata[1]}} s<extra></extra>",
        )
    fig.update_layout(barmode="overlay", bargap=0.25, legend=dict(orientation="v", x=1.01, y=1, yanchor="top"))
    fig.update_yaxes(categoryorder="array", categoryarray=ids, autorange="reversed", showgrid=False)
    # Empty bars keep machines that never ran on the chart, so missing work is visible
    fig.add_bar(y=ids, x=[0] * len(ids), orientation="h", showlegend=False, hoverinfo="skip")
    _style(fig, 80 + 22 * len(ids), "Time (s)", None, hover="closest")
    fig.update_layout(legend=dict(orientation="v", x=1.01, y=1, yanchor="top"))
    return fig


def _stock_figure(rec: Recorder) -> go.Figure | None:
    stock = rec.stock_frame()
    changing = [c for c in stock.columns if stock[c].min() != stock[c].max()]
    if not changing:
        return None
    step = max(1, len(stock) // 1500)
    stock = stock.iloc[::step]
    cols = 3
    rows = math.ceil(len(changing) / cols)
    fig = make_subplots(
        rows=rows, cols=cols, subplot_titles=changing, shared_xaxes=True, vertical_spacing=0.12 / rows * 2
    )
    for i, name in enumerate(changing):
        fig.add_scatter(
            x=stock.index,
            y=stock[name],
            name=name,
            line=dict(color=SERIES[0], width=1.5, shape="hv"),
            showlegend=False,
            hovertemplate=f"{name}: %{{y:,.0f}}<extra>%{{x}} s</extra>",
            row=i // cols + 1,
            col=i % cols + 1,
        )
    _style(fig, 60 + 190 * rows, None, None, hover="closest")
    fig.update_annotations(font=dict(size=12, color=INK))
    return fig


def write_report(
    out: Path,
    rec: Recorder,
    policy: str,
    refs: dict[str, Recorder] | None = None,
    note: str = "",
    seed: int | None = None,
) -> Path:
    """One page about one episode, with the fixed rules' episodes on the same orders for comparison"""
    out = Path(out)
    _ensure_plotly(out.parent)
    refs = refs or {}
    sc = rec.scenario
    s = rec.summary()
    ref_s = {k: r.summary() for k, r in refs.items()}
    keep = ref_s.get("keep")
    from sjfactory.evaluate import cash_curve

    curves = {policy: cash_curve(rec), **{k: cash_curve(r) for k, r in refs.items()}}
    d = rec.deliveries_frame()
    per_product = (
        d.groupby("product")[["ordered", "shipped"]].sum() if not d.empty else pd.DataFrame()
    )
    product_text = ", ".join(
        f"{p}: {row.shipped:.0f} of {row.ordered:.0f}" for p, row in per_product.iterrows()
    )

    tiles = "".join(
        [
            _tile("Profit (cash gained)", _money(s["profit"]), _delta(s["profit"], keep and keep["profit"], "keep")),
            _tile(
                "Order units shipped",
                _pct(s["fill_rate"]),
                f"{s['units_shipped']:.0f} of {s['units_ordered']:.0f} units",
            ),
            _tile("Revenue", _money(s["revenue"])),
            _tile("Penalties", _money(s["penalty"])),
            _tile("Machines busy", _pct(s["machine_busy_ratio"]), "share of machine-seconds running"),
        ]
    )
    compare_rows = "".join(
        f"<tr><td>{POLICY_LABEL.get(k, k)}</td><td class='num'>{_money(v['profit'])}</td>"
        f"<td class='num'>{_pct(v['fill_rate'])}</td><td class='num'>{_money(v['revenue'])}</td>"
        f"<td class='num'>{_money(v['penalty'])}</td><td class='num'>{_pct(v['machine_busy_ratio'])}</td></tr>"
        for k, v in {policy: s, **ref_s}.items()
    )
    compare_table = (
        "<table><tr><th>Policy</th><th class='num'>Profit</th><th class='num'>Units shipped</th>"
        f"<th class='num'>Revenue</th><th class='num'>Penalties</th><th class='num'>Busy</th></tr>{compare_rows}</table>"
    )

    stock_fig = _stock_figure(rec)
    flow = (
        '<details><summary>Material flow chart</summary><img src="material_flow.png" alt="material flow"></details>'
        if (out / "material_flow.png").exists()
        else ""
    )
    body = f"""
<header>
  <nav><a href="../index.html">← All runs</a>{'<a href="training.html">Training progress</a>' if (out / 'training.html').exists() else ''}</nav>
  <h1>{html.escape(out.name)} · {POLICY_LABEL.get(policy, policy)}</h1>
  <div class="meta">One episode{f', seed {seed}' if seed is not None else ''} · {len(sc.machines)} machines · {s['seconds']:,} s · {html.escape(note)}</div>
</header>
<div class="tiles">{tiles}</div>
{_section("Cash over time", "Every policy faces the same orders. Higher at the right end is better. The flat gray line is the starting cash.", _chart(_cash_figure(curves, sc.initial_cash)))}
{_section("Compared with the fixed rules", "Same orders, same length of run.", compare_table)}
<div class="grid2">
{_section("Where the money came from and went", "Running totals. Revenue only arrives when an order is due and units are in stock. Running costs are energy, storage and rent; penalties are fines for missing units.", _chart(_money_figure(rec)))}
{_section("Orders", f"One mark per order, placed at its due time. Bigger mark = more units. {html.escape(product_text)}", _chart(_orders_figure(rec)))}
</div>
{_section("Machine schedule", "One row per machine. A colored bar means the machine was running that recipe; gaps mean it was idle (no recipe or no input stock).", _chart(_gantt_figure(rec)))}
{_section("Stock of materials that changed", "Each panel has its own scale.", _chart(stock_fig)) if stock_fig else ""}
<section><h2>Files</h2><p class="how">
<a href="summary.json">summary.json</a> · <a href="history.xlsx">history.xlsx</a> (every second) · <a href="dashboard.png">dashboard.png</a> · <a href="gantt.png">gantt.png</a></p>{flow}</section>
"""
    path = out / "report.html"
    path.write_text(_page(f"{out.name} report", body, "../plotly.min.js"), encoding="utf-8")
    return path


# Training page


def _health_figure(x, y, color=SERIES[0], ytitle=None, band=None) -> go.Figure:
    fig = go.Figure()
    if band is not None:
        fig.add_hrect(y0=band[0], y1=band[1], fillcolor=GOOD, opacity=0.08, line_width=0)
    fig.add_scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2), showlegend=False, hovertemplate="%{y:.3g}")
    return _style(fig, 220, "Training steps", ytitle)


def _eval_by_mode(ev: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """eval.csv -> {mode: one row per check (mean over test seeds, plus min and max profit)}"""
    if ev.empty:
        return {}
    if "mode" not in ev:  # runs from before both modes were tested
        ev = ev.assign(mode="fixed")
    return {
        mode: g.groupby("step").agg(
            profit=("profit", "mean"),
            low=("profit", "min"),
            high=("profit", "max"),
            fill_rate=("fill_rate", "mean"),
            busy=("busy", "mean"),
            revenue=("revenue", "mean"),
            penalty=("penalty", "mean"),
        )
        for mode, g in ev.groupby("mode", sort=False)
    }


def write_training_page(out: Path) -> Path:
    """Build training.html from the files the training monitor writes. Safe to call at any time."""
    out = Path(out)
    _ensure_plotly(out.parent)
    cfg = _read_json(out / "config.json", {})
    status = _read_json(out / "status.json", {"done": False, "step": 0})
    baselines = _read_json(out / "baselines.json", {})
    ev = pd.read_csv(out / "eval.csv") if (out / "eval.csv").exists() else pd.DataFrame()
    try:
        progress = pd.read_csv(out / "logs" / "progress.csv")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        progress = pd.DataFrame()
    reward_scale = cfg.get("reward_scale", 0.01)
    total = cfg.get("steps", 0)
    step = status.get("step", 0)
    done = status.get("done", False)

    aggs = _eval_by_mode(ev)
    keep = baselines.get("keep", {}).get("profit")
    rnd = baselines.get("random", {}).get("profit")

    # Tiles
    if aggs:
        best_mode = max(aggs, key=lambda m: aggs[m]["profit"].max())
        best_step = aggs[best_mode]["profit"].idxmax()
        best = aggs[best_mode].loc[best_step]
        tiles = [
            _tile("Best profit so far", _money(best["profit"]),
                  f"step {best_step:,}, {MODE_LABEL.get(best_mode, best_mode)} · {_delta(best['profit'], keep, 'keep')}"),
        ]
        for mode, agg in aggs.items():
            latest = agg.iloc[-1]
            tiles.append(
                _tile(f"Latest profit, {MODE_LABEL.get(mode, mode)}", _money(latest["profit"]),
                      f"{_pct(latest['fill_rate'])} of units shipped · {_delta(latest['profit'], keep, 'keep')}")
            )
        tiles.append(_tile("Fixed-rule baselines", _money(keep),
                           f"keep ({_pct(baselines.get('keep', {}).get('fill_rate'))} shipped) · random: {_money(rnd)}"))
        tiles = "".join(tiles)
    else:
        tiles = _tile("Waiting", "–", "the first evaluation has not finished yet")

    # Main chart: profit per evaluation, with the spread across seeds and the baselines
    fig = go.Figure()
    for mode, agg in aggs.items():
        x = agg.index.to_numpy()
        fig.add_scatter(
            x=np.r_[x, x[::-1]],
            y=np.r_[agg["high"], agg["low"][::-1]],
            mode="lines",
            fill="toself",
            fillcolor="rgba(42,120,214,0.15)" if mode == "fixed" else "rgba(42,120,214,0.07)",
            line=dict(width=0),
            name=f"Range over test seeds, {MODE_LABEL.get(mode, mode)}",
            hoverinfo="skip",
        )
        fig.add_scatter(
            x=x,
            y=agg["profit"],
            mode="lines+markers",
            name=f"Trained model, {MODE_LABEL.get(mode, mode)}",
            line=dict(color=POLICY_COLOR["model"], width=2, dash=MODE_DASH.get(mode, "solid")),
            marker=dict(size=8, symbol="circle" if mode == "fixed" else "diamond", line=dict(color=SURFACE, width=2)),
            hovertemplate="%{y:,.0f}",
        )
    if aggs:
        fig.add_scatter(
            x=[best_step],
            y=[best["profit"]],
            mode="markers+text",
            text=["best"],
            textposition="top center",
            marker=dict(size=14, color=POLICY_COLOR["model"], symbol="star", line=dict(color=SURFACE, width=2)),
            showlegend=False,
            hoverinfo="skip",
        )
    if "rollout/ep_rew_mean" in progress:
        p = progress.dropna(subset=["rollout/ep_rew_mean"])
        fig.add_scatter(
            x=p["time/total_timesteps"],
            y=p["rollout/ep_rew_mean"] / reward_scale,
            mode="lines",
            name="While training (with exploration)",
            line=dict(color=MUTED, width=1.5),
            hovertemplate="%{y:,.0f}",
        )
    for name, value in (("keep", keep), ("random", rnd)):
        if value is not None:
            fig.add_hline(
                y=value,
                line=dict(color=POLICY_COLOR[name], width=2),
                annotation_text=POLICY_LABEL[name],
                annotation_position="top left",
                annotation_font_color=INK2,
            )
    _style(fig, 380, "Training steps", "Profit per episode")
    if total:
        fig.update_xaxes(range=[0, total * 1.02])

    # Side charts from evaluations
    def eval_line(col, ytitle, base_key, pct=False):
        f = go.Figure()
        for mode, agg in aggs.items():
            f.add_scatter(
                x=agg.index,
                y=agg[col] * (100 if pct else 1),
                mode="lines+markers",
                name=f"Model, {MODE_LABEL.get(mode, mode)}",
                line=dict(color=POLICY_COLOR["model"], width=2, dash=MODE_DASH.get(mode, "solid")),
                marker=dict(size=7, symbol="circle" if mode == "fixed" else "diamond", line=dict(color=SURFACE, width=2)),
                hovertemplate="%{y:,.1f}",
            )
        for name in ("keep", "random"):
            v = baselines.get(name, {}).get(base_key)
            if v is not None:
                f.add_hline(y=v * (100 if pct else 1), line=dict(color=POLICY_COLOR[name], width=2))
        _style(f, 240, "Training steps", ytitle)
        f.update_layout(showlegend=False)
        return f

    money = go.Figure()
    for mode, agg in aggs.items():
        for key, label in (("revenue", "Revenue"), ("penalty", "Penalties")):
            money.add_scatter(
                x=agg.index,
                y=agg[key],
                mode="lines+markers",
                name=f"{label}, {MODE_LABEL.get(mode, mode)}",
                line=dict(color=MONEY_COLOR[key], width=2, dash=MODE_DASH.get(mode, "solid")),
                marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                hovertemplate="%{y:,.0f}",
            )
    _style(money, 240, "Training steps", "Per episode")

    # Learning health from Stable-Baselines3's log
    health = []
    if not progress.empty and "time/total_timesteps" in progress:
        x = progress["time/total_timesteps"]
        specs = [
            ("train/entropy_loss", -1, "Choice randomness (entropy)",
             "How unsure the model still is. It should fall slowly. A sudden drop to near 0 means it stopped exploring too early.", None),
            ("train/explained_variance", 1, "Reward prediction quality",
             "How well the model predicts the reward it will get (1 = perfect, 0 = no better than guessing). Should rise toward 1.", (0.5, 1.0)),
            ("train/approx_kl", 1, "Size of each update",
             "How much the decisions changed in one update. Spikes above about 0.05 mean training is unstable; lower the learning rate.", (0, 0.05)),
            ("train/value_loss", 1, "Reward prediction error",
             "Error of the reward predictions. Big swings are normal early; it should calm down over time.", None),
        ]
        for col, sign, title, how, band in specs:
            if col in progress:
                ok = progress[col].notna()
                health.append(_section(title, how, _chart(_health_figure(x[ok], sign * progress[col][ok], band=band))))

    # Latest test episode against the baselines, same orders
    curves = {}
    latest_curves = _read_json(out / "latest_curve.json", {})
    if "time" in latest_curves:  # runs from before both modes were tested
        latest_curves = {"fixed": latest_curves}
    for mode, c in latest_curves.items():
        curves[f"model:{mode}"] = c
    for name in ("keep", "random"):
        if "curve" in baselines.get(name, {}):
            curves[name] = baselines[name]["curve"]

    pct_done = min(100, 100 * step / total) if total else 0
    badge = (
        '<span class="badge done">Finished</span>'
        if done
        else f'<span class="badge live">Running · reloads every {REFRESH_SECONDS} s</span>'
    )
    report_link = '<a href="report.html">Final model report</a>' if (out / "report.html").exists() else ""
    args_text = " · ".join(
        f"{k} {v}" for k, v in cfg.items() if k in ("steps", "envs", "ticks", "gamma", "horizon", "seed")
    )
    body = f"""
<header>
  <nav><a href="../index.html">← All runs</a>{report_link}</nav>
  <h1>{html.escape(out.name)} · training {badge}</h1>
  <div class="meta">Step {step:,} of {total:,} ({pct_done:.0f}%) · {html.escape(args_text)} · {html.escape(cfg.get('note', ''))}</div>
</header>
<div class="tiles">{tiles}</div>
{_section("Is it learning? Profit per test episode", "Every few thousand steps the model plays the same test orders twice: solid blue always takes its most likely choice, dashed blue draws choices at random from its probabilities, as in training. Blue above the orange line beats the fixed rule. A big gap between solid and dashed means the model relies on chance to spread its machines over recipes. Shaded bands: best and worst test episode. Gray: the score while training.", _chart(fig))}
<div class="grid2">
{_section("Order units shipped (%)", "Share of ordered units that were in stock when due, mean over the test seeds. Blue solid / dashed = model without / with randomness; orange = keep; aqua = random.", _chart(eval_line("fill_rate", "%", "fill_rate", pct=True)))}
{_section("Machines busy (%)", "Share of machine-seconds spent running. Busy is not always good: making the wrong thing costs money.", _chart(eval_line("busy", "%", "machine_busy_ratio", pct=True)))}
{_section("Revenue and penalties per test episode", "Penalties fall when fewer ordered units are missing.", _chart(money))}
{_section("Latest test episode: cash over time", "First test seed. Same orders for every policy.", _chart(_cash_figure(curves, cfg.get("initial_cash", 0))) if curves else "")}
</div>
<h2 style="margin-top:28px">Learning health</h2>
<p class="how" style="color:{INK2}">Checks that the training itself is working. Green bands show the healthy range where there is one.</p>
<div class="grid2">{"".join(health) or "<p>No training statistics yet.</p>"}</div>
"""
    path = out / "training.html"
    page = _page(f"{out.name} training", body, "../plotly.min.js", None if done else REFRESH_SECONDS)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(page, encoding="utf-8")
    tmp.replace(path)  # a browser reloading mid-write never sees half a page
    return path


# Index of all runs


def write_index(runs_dir: Path) -> Path:
    runs_dir = Path(runs_dir)
    _ensure_plotly(runs_dir)
    rows = []
    for d in sorted((p for p in runs_dir.iterdir() if p.is_dir()), reverse=True):
        summary = _read_json(d / "summary.json")
        cfg = _read_json(d / "config.json", {})
        if summary is None and not (d / "eval.csv").exists():
            continue
        summary = summary or {}
        rows.append(
            {
                "name": d.name,
                "kind": cfg.get("kind", d.name.split("-", 1)[-1]),
                "note": cfg.get("note", ""),
                "profit": summary.get("profit"),
                "fill_rate": summary.get("fill_rate"),
                "busy": summary.get("machine_busy_ratio"),
                "seconds": summary.get("seconds"),
                "report": (d / "report.html").exists(),
                "training": (d / "training.html").exists(),
                "eval": d / "eval.csv",
            }
        )

    # Training curves of every run (the better test mode at each check): the newest in blue, older ones in gray
    fig = go.Figure()
    newest_done = False
    for r in rows:
        if not r["eval"].exists():
            continue
        ev = pd.concat([a["profit"] for a in _eval_by_mode(pd.read_csv(r["eval"])).values()], axis=1).max(axis=1)
        newest = not newest_done
        newest_done = True
        fig.add_scatter(
            x=ev.index,
            y=ev.values,
            mode="lines+markers",
            name=f"{r['name']} {r['note']}".strip(),
            line=dict(color=POLICY_COLOR["model"] if newest else AXIS, width=2.5 if newest else 1.5),
            marker=dict(size=6),
            opacity=1 if newest else 0.9,
            hovertemplate="%{y:,.0f}",
        )
    _style(fig, 360, "Training steps", "Test profit per episode", hover="closest")

    table_rows = ""
    for r in rows:
        links = [f'<a href="{r["name"]}/{page}.html">{page}</a>' for page in ("report", "training") if r[page]]
        seconds = "" if r["seconds"] is None else f"{r['seconds']:,}"
        table_rows += (
            f"<tr><td>{html.escape(r['name'])}</td><td>{html.escape(r['kind'])}</td><td>{html.escape(r['note'])}</td>"
            f"<td class='num'>{_money(r['profit'])}</td><td class='num'>{_pct(r['fill_rate'])}</td>"
            f"<td class='num'>{_pct(r['busy'])}</td><td class='num'>{seconds}</td><td>{' '.join(links)}</td></tr>"
        )
    body = f"""
<header><h1>All runs</h1><div class="meta">{len(rows)} runs in {html.escape(str(runs_dir))} · newest first</div></header>
{_section("Training runs compared", "Test profit during each training run. The newest run is blue; older runs are gray. Hover a line to see its name.", _chart(fig)) if fig.data else ""}
<section><h2>Runs</h2><p class="how">Profit and shipped share come from the run's final episode.</p>
<table><tr><th>Run</th><th>Type</th><th>Note</th><th class="num">Profit</th><th class="num">Units shipped</th>
<th class="num">Busy</th><th class="num">Seconds</th><th>Pages</th></tr>{table_rows}</table></section>
"""
    path = runs_dir / "index.html"
    path.write_text(_page("sjfactory runs", body, "plotly.min.js"), encoding="utf-8")
    return path
