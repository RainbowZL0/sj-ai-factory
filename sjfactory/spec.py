"""Scenario: the fixed description of a factory (materials, recipes, machines, money rules, orders).

A scenario never changes after loading. Everything that changes over time lives in sim.State.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCENARIO = PROJECT_ROOT / "scenarios" / "default.yaml"


@dataclass(frozen=True)
class Material:
    name: str
    initial_stock: float = 0.0
    sell_price: float = 0.0  # income per unit when an order is delivered
    storage_cost: float = 0.0  # cost per unit per second
    shortfall_penalty: float = 0.0  # fine per unit missing when an order is due


@dataclass(frozen=True)
class Recipe:
    name: str
    category: str  # which kind of machine can run it
    cycle_time: int  # seconds per batch
    power_kw: float
    inputs: dict[str, float]  # used per batch
    outputs: dict[str, float]  # made per batch


@dataclass(frozen=True)
class Machine:
    id: str
    category: str
    initial_recipe: str | None  # None means the machine starts stopped


@dataclass(frozen=True)
class Order:
    product: str
    quantity: float
    due_time: int  # absolute time in seconds; ships whatever stock exists at that moment


@dataclass(frozen=True)
class RandomOrders:
    """Extra orders generated from the random seed at each reset"""

    count: int
    products: tuple[str, ...]
    quantity_range: tuple[int, int]  # both ends included


@dataclass(frozen=True)
class Scenario:
    horizon: int  # seconds per episode
    initial_cash: float
    energy_price: float  # per kWh
    rent_per_second: float
    materials: tuple[Material, ...]
    recipes: tuple[Recipe, ...]
    machines: tuple[Machine, ...]
    orders: tuple[Order, ...] = ()
    random_orders: RandomOrders | None = None

    def __post_init__(self):
        self._validate()

    @cached_property
    def material_index(self) -> dict[str, int]:
        return {m.name: i for i, m in enumerate(self.materials)}

    @cached_property
    def recipe_index(self) -> dict[str, int]:
        return {r.name: i for i, r in enumerate(self.recipes)}

    @cached_property
    def products(self) -> tuple[str, ...]:
        """Materials that can appear in orders, in material-list order"""
        names = {o.product for o in self.orders}
        if self.random_orders:
            names |= set(self.random_orders.products)
        return tuple(m.name for m in self.materials if m.name in names)

    def recipes_for(self, category: str) -> tuple[int, ...]:
        """Indexes of the recipes a machine category can run"""
        return tuple(i for i, r in enumerate(self.recipes) if r.category == category)

    def _validate(self):
        def check_unique(kind, names):
            seen = set()
            for n in names:
                if n in seen:
                    raise ValueError(f"duplicate {kind} name: {n}")
                seen.add(n)

        check_unique("material", (m.name for m in self.materials))
        check_unique("recipe", (r.name for r in self.recipes))
        check_unique("machine", (m.id for m in self.machines))
        if self.horizon < 1:
            raise ValueError("horizon must be at least 1")

        materials = {m.name for m in self.materials}
        recipes = {r.name: r for r in self.recipes}
        for r in self.recipes:
            if r.cycle_time < 1:
                raise ValueError(f"recipe {r.name}: cycle_time must be at least 1")
            for name in (*r.inputs, *r.outputs):
                if name not in materials:
                    raise ValueError(f"recipe {r.name} uses unknown material {name}")
        for m in self.machines:
            if m.initial_recipe is None:
                continue
            r = recipes.get(m.initial_recipe)
            if r is None:
                raise ValueError(f"machine {m.id}: starting recipe {m.initial_recipe} does not exist")
            if r.category != m.category:
                raise ValueError(f"machine {m.id} ({m.category}) cannot run recipe {r.name} ({r.category})")
        for o in self.orders:
            if o.product not in materials:
                raise ValueError(f"order product {o.product} is not a known material")
        if self.random_orders:
            for p in self.random_orders.products:
                if p not in materials:
                    raise ValueError(f"random order product {p} is not a known material")
            lo, hi = self.random_orders.quantity_range
            if not 0 <= lo <= hi:
                raise ValueError("random order quantity range must satisfy 0 <= low <= high")


def load_scenario(path: str | Path = DEFAULT_SCENARIO) -> Scenario:
    data = YAML(typ="safe").load(Path(path).read_text(encoding="utf-8"))
    return scenario_from_dict(data)


def scenario_from_dict(d: dict[str, Any]) -> Scenario:
    materials = tuple(
        Material(name=name, **(fields or {})) for name, fields in d["materials"].items()
    )
    recipes = tuple(
        Recipe(
            name=name,
            category=r["category"],
            cycle_time=int(r["cycle_time"]),
            power_kw=float(r.get("power_kw", 0.0)),
            inputs=dict(r.get("inputs") or {}),
            outputs=dict(r.get("outputs") or {}),
        )
        for name, r in d["recipes"].items()
    )
    orders = d.get("orders") or {}
    rnd = orders.get("random")
    return Scenario(
        horizon=int(d["horizon"]),
        initial_cash=float(d.get("initial_cash", 0.0)),
        energy_price=float(d.get("energy_price", 0.0)),
        rent_per_second=float(d.get("rent_per_second", 0.0)),
        materials=materials,
        recipes=recipes,
        machines=_expand_machines(d["machines"]),
        orders=tuple(Order(**o) for o in orders.get("fixed") or []),
        random_orders=(
            RandomOrders(
                count=int(rnd["count"]),
                products=tuple(rnd["products"]),
                quantity_range=tuple(rnd["quantity"]),
            )
            if rnd
            else None
        ),
    )


def _expand_machines(groups: list[dict]) -> tuple[Machine, ...]:
    """Expand "category + starting recipe + count" groups into single machines, numbered like CASTER-01"""
    counters: dict[str, int] = {}
    machines = []
    for g in groups:
        cat = g["category"]
        for _ in range(int(g.get("count", 1))):
            counters[cat] = counters.get(cat, 0) + 1
            machines.append(
                Machine(
                    id=f"{cat.upper()}-{counters[cat]:02d}",
                    category=cat,
                    initial_recipe=g.get("recipe"),
                )
            )
    return tuple(machines)
