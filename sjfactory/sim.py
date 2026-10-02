"""Factory simulation: the state, and the rule that moves it forward one second.

There is no decision logic here. Which recipe each machine runs (fixed rule, random,
reinforcement learning) is decided outside and passed in through step(changes).
"""

from __future__ import annotations

import dataclasses
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
    remaining: np.ndarray  # [machine], seconds left in the current batch, 0 means no batch
    setup: np.ndarray  # [machine], seconds left in a recipe changeover; a machine in changeover makes nothing
    orders: list[Order]  # orders not yet delivered, sorted by due time
    down: np.ndarray  # [machine], seconds left broken down; a broken machine does nothing
    failures: list[tuple[int, int, int]]  # breakdowns still to come: (time, machine, seconds out), sorted by time


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
        self.order_fine = np.array([m.order_fine for m in sc.materials], dtype=float)

        # Sort key per recipe for handing out inputs (lower goes first); None keeps machine order
        self.input_rank = -np.array(sc.recipe_depth) if sc.input_priority == "downstream" else None

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
            setup=np.zeros(self.n_machines, dtype=int),
            orders=orders,
            down=np.zeros(self.n_machines, dtype=int),
            failures=self._failures(seed),
        )
        return self.state

    def _failures(self, seed: int | None) -> list[tuple[int, int, int]]:
        """Breakdown times for the episode, from their own random stream so the orders don't change"""
        spec = self.scenario.breakdowns
        if spec is None or spec.per_hour == 0:
            return []
        rng = np.random.default_rng(None if seed is None else [seed, 1])
        failures = []
        for m in range(self.n_machines):
            for _ in range(rng.poisson(spec.per_hour * self.scenario.horizon / 3600)):
                at = int(rng.integers(0, self.scenario.horizon))
                failures.append((at, m, int(rng.integers(spec.duration_range[0], spec.duration_range[1] + 1))))
        return sorted(failures)

    def _random_orders(self, rng: np.random.Generator) -> list[Order]:
        spec = self.scenario.random_orders
        if spec is None:
            return []
        # Draws for the optional settings only happen when they are set, so older scenarios get the same orders
        lo, hi = spec.count_range
        count = lo if lo == hi else int(rng.integers(lo, hi + 1))
        products = sorted(set(spec.products), key=spec.products.index)
        share = None  # None: every product in the list equally likely, as always
        if spec.mix == "random":
            if rng.random() < 0.25:
                share = np.eye(len(products))[rng.integers(len(products))]
            else:
                share = rng.dirichlet(np.ones(len(products)))
        first_due = spec.notice_range[0] if spec.notice_range else 0

        orders = []
        for _ in range(count):
            product = str(rng.choice(spec.products)) if share is None else str(rng.choice(products, p=share))
            quantity = int(rng.integers(spec.quantity_range[0], spec.quantity_range[1] + 1))
            due = int(rng.integers(first_due, self.scenario.horizon))
            known = 0
            if spec.notice_range:
                notice = int(rng.integers(spec.notice_range[0], spec.notice_range[1] + 1))
                known = max(0, due - notice)
            orders.append(Order(product=product, quantity=quantity, due_time=due, known_time=known))
        return orders

    def decline(self, position: int):
        """Give up the order at this position in state.orders: when due it ships nothing and is fined as a short
        order, and the stock stays for other orders. Without this, every due order takes stock if it can."""
        o = self.state.orders[position]
        self.state.orders[position] = dataclasses.replace(o, declined=True)

    @property
    def idle(self) -> np.ndarray:
        """[machine] True if the machine is not running a batch, not in a changeover and not broken, so it may
        switch recipe"""
        return (self.state.remaining == 0) & (self.state.setup == 0) & (self.state.down == 0)

    @property
    def done(self) -> bool:
        return self.state.clock >= self.scenario.horizon

    def step(self, changes: Mapping[int, int] | None = None) -> StepReport:
        """Move forward 1 second.

        :param changes: {machine index: new recipe index or STOP}. Only idle machines can change.
            Machines not listed keep their recipe: when idle, they start as soon as inputs are in stock.
        """
        s, sc = self.state, self.scenario

        # 1. Switch recipes: only idle machines can switch. A different recipe needs a changeover first
        idle = self.idle
        for m, r in (changes or {}).items():
            if not idle[m]:
                raise ValueError(f"{sc.machines[m].id} is busy and cannot switch recipe")
            if r != STOP and r not in self.allowed[m]:
                raise ValueError(f"{sc.machines[m].id} cannot run recipe {sc.recipes[r].name}")
            if r != STOP and r != s.recipe[m]:
                s.setup[m] = sc.changeover_time
            s.recipe[m] = r

        # 1b. Machines due to break down stop now, after switching, so a switch asked for this second still
        #     happens (a breakdown on a broken machine makes it last longer)
        while s.failures and s.failures[0][0] <= s.clock:
            _, m, seconds = s.failures.pop(0)
            s.down[m] = max(s.down[m], seconds)
        working = s.down == 0

        # 2. Idle machines with a recipe start if inputs are in stock. First come, first served, in machine order,
        #    or with input_priority "downstream" the machines furthest from the raw materials first
        waiting = np.flatnonzero(self.idle & (s.recipe != STOP))
        if self.input_rank is not None and len(waiting) > 1:
            waiting = waiting[np.argsort(self.input_rank[s.recipe[waiting]], kind="stable")]
        if len(waiting):
            # Machines short of inputs now stay short (starting only uses stock up), so only the rest are checked
            # one by one. Same result as checking every machine in order, much faster.
            need = self.recipe_in[s.recipe[waiting]]
            for m, n in zip(waiting[(s.stock >= need).all(axis=1)], need[(s.stock >= need).all(axis=1)]):
                if (s.stock >= n).all():
                    s.stock -= n
                    s.remaining[m] = self.cycle_time[s.recipe[m]]

        running = (s.remaining > 0) & working
        running_recipe = np.where(running, s.recipe, STOP)
        energy_kwh = float(self.power_kw[s.recipe[running]].sum()) / 3600

        # 3. Advance 1 second; changeovers count down; finished batches go into stock
        s.setup[(s.setup > 0) & working] -= 1
        s.down[~working] -= 1
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
            if (not sc.partial_delivery and shipped < o.quantity) or o.declined:
                shipped = 0  # all or nothing: a short order ships nothing and is fined in full
            s.stock[i] -= shipped
            deliveries.append(
                Delivery(
                    order=o,
                    shipped=float(shipped),
                    revenue=float(shipped * self.sell_price[i]),
                    penalty=float((o.quantity - shipped) * self.shortfall_penalty[i])
                    + (float(self.order_fine[i]) if shipped < o.quantity else 0.0),
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
