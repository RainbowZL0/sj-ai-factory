"""Factory simulation: the state, and the rule that moves it forward one second.

There is no decision logic here. Which recipe each machine runs (fixed rule, random,
reinforcement learning) is decided outside and passed in through step(changes).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import numpy as np

from sjfactory.spec import Order, Scenario

STOP = -1  # recipe index meaning "stopped, no recipe"


@dataclass
class State:
    clock: int  # seconds passed
    cash: float
    stock: np.ndarray  # [material], amount in stock
    recipe: np.ndarray  # [machine], index of the assigned recipe, STOP if stopped
    remaining: np.ndarray  # [machine], seconds left in the current batch, 0 means idle
    orders: list[Order]  # orders not yet delivered, sorted by due time


@dataclass(frozen=True)
class Delivery:
    order: Order
    shipped: float
    revenue: float
    penalty: float


@dataclass(frozen=True)
class StepReport:
    """What happened during one step. All money amounts are for this step only."""

    clock: int  # time at the end of this step
    running: np.ndarray  # [machine], recipe running this step, STOP if not running
    energy_kwh: float
    energy_cost: float
    revenue: float
    penalty: float
    storage_cost: float
    rent: float
    deliveries: tuple[Delivery, ...]

    @property
    def cash_change(self) -> float:
        return self.revenue - self.penalty - self.energy_cost - self.storage_cost - self.rent


class FactorySim:
    def __init__(self, scenario: Scenario):
        self.scenario = sc = scenario
        mi = sc.material_index
        n_mat, n_rcp = len(sc.materials), len(sc.recipes)

        # Recipe matrices: one row per recipe, one column per material
        self.recipe_in = np.zeros((n_rcp, n_mat))
        self.recipe_out = np.zeros((n_rcp, n_mat))
        for r, rcp in enumerate(sc.recipes):
            for name, q in rcp.inputs.items():
                self.recipe_in[r, mi[name]] = q
            for name, q in rcp.outputs.items():
                self.recipe_out[r, mi[name]] = q
        self.cycle_time = np.array([r.cycle_time for r in sc.recipes], dtype=int)
        self.power_kw = np.array([r.power_kw for r in sc.recipes], dtype=float)

        self.sell_price = np.array([m.sell_price for m in sc.materials], dtype=float)
        self.storage_cost = np.array([m.storage_cost for m in sc.materials], dtype=float)
        self.shortfall_penalty = np.array([m.shortfall_penalty for m in sc.materials], dtype=float)

        # Recipe indexes each machine can run
        self.allowed = tuple(sc.recipes_for(m.category) for m in sc.machines)
        self.n_machines = len(sc.machines)

        # Called as f(state, report) after each step, e.g. to record history; never changes the simulation
        self.listeners: list[Callable[[State, StepReport], None]] = []
        self.state: State | None = None

    def reset(self, seed: int | None = None) -> State:
        sc = self.scenario
        rng = np.random.default_rng(seed)
        orders = sorted(
            [*sc.orders, *self._random_orders(rng)], key=lambda o: o.due_time
        )
        self.state = State(
            clock=0,
            cash=sc.initial_cash,
            stock=np.array([m.initial_stock for m in sc.materials], dtype=float),
            recipe=np.array(
                [
                    STOP if m.initial_recipe is None else sc.recipe_index[m.initial_recipe]
                    for m in sc.machines
                ],
                dtype=int,
            ),
            remaining=np.zeros(self.n_machines, dtype=int),
            orders=orders,
        )
        return self.state

    def _random_orders(self, rng: np.random.Generator) -> list[Order]:
        spec = self.scenario.random_orders
        if spec is None:
            return []
        lo, hi = spec.quantity_range
        return [
            Order(
                product=str(rng.choice(spec.products)),
                quantity=int(rng.integers(lo, hi + 1)),
                due_time=int(rng.integers(0, self.scenario.horizon)),
            )
            for _ in range(spec.count)
        ]

    @property
    def done(self) -> bool:
        return self.state.clock >= self.scenario.horizon

    def step(self, changes: Mapping[int, int] | None = None) -> StepReport:
        """Move forward 1 second.

        :param changes: {machine index: new recipe index or STOP}. Only idle machines can change.
            Machines not listed keep their recipe: when idle, they start as soon as inputs are in stock.
        """
        s, sc = self.state, self.scenario

        # 1. Switch recipes: only idle machines can switch
        for m, r in (changes or {}).items():
            if s.remaining[m] > 0:
                raise ValueError(f"{sc.machines[m].id} is busy and cannot switch recipe")
            if r != STOP and r not in self.allowed[m]:
                raise ValueError(f"{sc.machines[m].id} cannot run recipe {sc.recipes[r].name}")
            s.recipe[m] = r

        # 2. Idle machines with a recipe start if inputs are in stock. First come, first served, in machine order
        for m in np.flatnonzero((s.remaining == 0) & (s.recipe != STOP)):
            need = self.recipe_in[s.recipe[m]]
            if np.all(s.stock >= need):
                s.stock -= need
                s.remaining[m] = self.cycle_time[s.recipe[m]]

        running = s.remaining > 0
        running_recipe = np.where(running, s.recipe, STOP)
        energy_kwh = float(self.power_kw[s.recipe[running]].sum()) / 3600

        # 3. Advance 1 second; finished batches go into stock
        s.remaining[running] -= 1
        for m in np.flatnonzero(running & (s.remaining == 0)):
            s.stock += self.recipe_out[s.recipe[m]]
        s.clock += 1

        # 4. Due orders ship from current stock; missing units are fined
        deliveries = []
        while s.orders and s.orders[0].due_time <= s.clock:
            o = s.orders.pop(0)
            i = sc.material_index[o.product]
            shipped = min(o.quantity, s.stock[i])
            s.stock[i] -= shipped
            deliveries.append(
                Delivery(
                    order=o,
                    shipped=float(shipped),
                    revenue=float(shipped * self.sell_price[i]),
                    penalty=float((o.quantity - shipped) * self.shortfall_penalty[i]),
                )
            )

        # 5. Settle cash
        report = StepReport(
            clock=s.clock,
            running=running_recipe,
            energy_kwh=energy_kwh,
            energy_cost=energy_kwh * sc.energy_price,
            revenue=sum(d.revenue for d in deliveries),
            penalty=sum(d.penalty for d in deliveries),
            storage_cost=float(self.storage_cost @ s.stock),
            rent=sc.rent_per_second,
            deliveries=tuple(deliveries),
        )
        s.cash += report.cash_change

        for f in self.listeners:
            f(s, report)
        return report
