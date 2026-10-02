"""Records the state and money of every step for charts and export. Only watches; never changes the simulation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sjfactory.sim import STOP, FactorySim, State, StepReport


class Recorder:
    """Usage:
    with Recorder(sim) as rec:
        ...run an episode...
    rec.save(out_dir)
    """

    def __init__(self, sim: FactorySim):
        self.sim = sim
        self.scenario = sim.scenario
        self.reports: list[StepReport] = []
        self.stock: list[np.ndarray] = []
        self.cash: list[float] = []

    def __enter__(self):
        self.sim.listeners.append(self._on_step)
        return self

    def __exit__(self, *exc):
        self.sim.listeners.remove(self._on_step)

    def _on_step(self, state: State, report: StepReport):
        self.reports.append(report)
        self.stock.append(state.stock.copy())
        self.cash.append(state.cash)

    @property
    def time(self) -> np.ndarray:
        return np.array([r.clock for r in self.reports])

    def scalars(self) -> pd.DataFrame:
        df = pd.DataFrame(
            {
                "time": self.time,
                "cash": self.cash,
                "cash_change": [r.cash_change for r in self.reports],
                "revenue": [r.revenue for r in self.reports],
                "penalty": [r.penalty for r in self.reports],
                "energy_kwh": [r.energy_kwh for r in self.reports],
                "energy_cost": [r.energy_cost for r in self.reports],
                "storage_cost": [r.storage_cost for r in self.reports],
                "rent": [r.rent for r in self.reports],
            }
        )
        df["total_energy_kwh"] = df["energy_kwh"].cumsum()
        return df

    def stock_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            np.array(self.stock),
            columns=[m.name for m in self.scenario.materials],
            index=pd.Index(self.time, name="time"),
        )

    def running_matrix(self) -> np.ndarray:
        """[step, machine], recipe running at each step, STOP if not running"""
        return np.array([r.running for r in self.reports])

    def gantt_frame(self) -> pd.DataFrame:
        names = np.array([r.name for r in self.scenario.recipes] + [None], dtype=object)
        return pd.DataFrame(
            names[self.running_matrix()],  # STOP=-1 picks the trailing None
            columns=[m.id for m in self.scenario.machines],
            index=pd.Index(self.time, name="time"),
        )

    def deliveries_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "time": r.clock,
                    "product": d.order.product,
                    "ordered": d.order.quantity,
                    "shipped": d.shipped,
                    "revenue": d.revenue,
                    "penalty": d.penalty,
                }
                for r in self.reports
                for d in r.deliveries
            ],
            columns=["time", "product", "ordered", "shipped", "revenue", "penalty"],
        )

    def summary(self) -> dict:
        s = self.scalars()
        d = self.deliveries_frame()
        busy = (self.running_matrix() != STOP).mean() if self.reports else 0.0
        return {
            "seconds": len(self.reports),
            "final_cash": float(s["cash"].iat[-1]) if len(s) else self.scenario.initial_cash,
            "revenue": float(s["revenue"].sum()),
            "penalty": float(s["penalty"].sum()),
            "energy_kwh": float(s["energy_kwh"].sum()),
            "orders_delivered": len(d),
            "units_ordered": float(d["ordered"].sum()),
            "units_shipped": float(d["shipped"].sum()),
            "machine_busy_ratio": float(busy),
        }

    def save(self, out_dir: str | Path) -> Path:
        """Save the Excel file and three charts to out_dir"""
        from sjfactory import plots

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(out / "history.xlsx") as xw:
            self.scalars().to_excel(xw, sheet_name="scalars", index=False)
            self.stock_frame().to_excel(xw, sheet_name="stock")
            self.deliveries_frame().to_excel(xw, sheet_name="deliveries", index=False)
            self.gantt_frame().to_excel(xw, sheet_name="gantt")
        plots.draw_dashboard(self, out / "dashboard.png")
        plots.draw_gantt(self, out / "gantt.png")
        plots.draw_material_flow(self.scenario, out / "material_flow.png")
        return out
