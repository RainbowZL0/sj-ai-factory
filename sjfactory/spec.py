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
DEFAULT_SCENARIO = PROJECT_ROOT / "scenarios" / "lab.yaml"


@dataclass(frozen=True)
class Material:
    name: str
    initial_stock: float = 0.0
    sell_price: float = 0.0  # income per unit when an order is delivered
    storage_cost: float = 0.0  # cost per unit per second
    shortfall_penalty: float = 0.0  # fine per unit missing when an order is due
    order_fine: float = 0.0  # extra fine per order of this material that is not filled in full when due


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
    known_time: int = 0  # when the order becomes known; before that the model can't see it


@dataclass(frozen=True)
class RandomOrders:
    """Extra orders generated from the random seed at each reset.

    Without count_range, mix or notice, orders are drawn exactly as they always were, so old results repeat.
    """

    count_range: tuple[int, int]  # number of orders, drawn per episode; both ends included
    products: tuple[str, ...]
    quantity_range: tuple[int, int]  # units per order; both ends included
    # "even": every order picks a product with equal chance. "random": each episode draws its own mix:
    # a quarter of episodes order only one product, the rest a random share of each.
    mix: str = "even"
    # Seconds between an order becoming known and its due time, drawn per order; both ends included.
    # None: every order is known from the start. Nothing is due before the shortest notice.
    notice_range: tuple[int, int] | None = None


@dataclass(frozen=True)
class Scenario:
    horizon: int  # seconds per episode
    initial_cash: float
    energy_price: float  # per kWh
    rent_per_second: float
    changeover_time: int  # seconds a machine makes nothing after switching to a different recipe
    materials: tuple[Material, ...]
    recipes: tuple[Recipe, ...]
    machines: tuple[Machine, ...]
    orders: tuple[Order, ...] = ()
    random_orders: RandomOrders | None = None
    # Which waiting machines get inputs first when stock is short. "machine_order": in the order machines are
    # listed. "downstream": machines whose recipe is further from the raw materials first, then list order.
    input_priority: str = "machine_order"
    # True: a due order ships whatever stock exists and is paid per unit shipped. False: it ships only if the full
    # quantity is in stock; otherwise nothing ships, nothing is paid and every unit of the order is fined.
    partial_delivery: bool = True

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

    @cached_property
    def obtainable(self) -> frozenset[str]:
        """Materials the factory can ever have: those in stock at the start, plus anything made from them"""
        have = {m.name for m in self.materials if m.initial_stock > 0}
        grew = True
        while grew:
            grew = False
            for r in self.recipes:
                if set(r.inputs) <= have and not set(r.outputs) <= have:
                    have |= set(r.outputs)
                    grew = True
        return frozenset(have)

    def can_ever_run(self, recipe: int) -> bool:
        """False if the recipe needs a material the factory can never get (ore, for example, is never bought)"""
        return set(self.recipes[recipe].inputs) <= self.obtainable

    @cached_property
    def recipe_depth(self) -> tuple[int, ...]:
        """Per recipe: 1 if all its inputs are raw (no recipe makes them), else 1 + the deepest recipe making an input"""
        makers: dict[str, list[int]] = {}
        for i, r in enumerate(self.recipes):
            for name in r.outputs:
                makers.setdefault(name, []).append(i)
        depth: dict[int, int] = {}

        def of(i: int, seen: frozenset[int]) -> int:
            if i not in depth:
                if i in seen:
                    raise ValueError(f"recipes around {self.recipes[i].name} go round in a circle")
                below = [of(j, seen | {i}) for name in self.recipes[i].inputs for j in makers.get(name, [])]
                depth[i] = 1 + max(below, default=0)
            return depth[i]

        return tuple(of(i, frozenset()) for i in range(len(self.recipes)))

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
        if self.changeover_time < 0:
            raise ValueError("changeover_time must not be negative")
        if self.input_priority not in ("machine_order", "downstream"):
            raise ValueError(f"input_priority must be machine_order or downstream, not {self.input_priority}")

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
            ro = self.random_orders
            lo, hi = ro.quantity_range
            if not 0 <= lo <= hi:
                raise ValueError("random order quantity range must satisfy 0 <= low <= high")
            lo, hi = ro.count_range
            if not 0 <= lo <= hi:
                raise ValueError("random order count range must satisfy 0 <= low <= high")
            if ro.mix not in ("even", "random"):
                raise ValueError(f"random order mix must be even or random, not {ro.mix}")
            if ro.notice_range is not None:
                lo, hi = ro.notice_range
                if not 0 <= lo <= hi or lo >= self.horizon:
                    raise ValueError("random order notice range must satisfy 0 <= low <= high, low < horizon")


def load_scenario(path: str | Path = DEFAULT_SCENARIO) -> Scenario:
    return scenario_from_dict(read_scenario_dict(path))


def read_scenario_dict(path: str | Path) -> dict[str, Any]:
    """The scenario file as a dict. A file with "base: other.yaml" starts from that file (path relative to this
    one) and changes only what it lists: nested mappings are merged key by key, anything else is replaced."""
    path = Path(path)
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
    base = data.pop("base", None)
    return _merge(read_scenario_dict(path.parent / base), data) if base else data


def _merge(base: dict, changes: dict) -> dict:
    out = dict(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


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
        changeover_time=int(d.get("changeover_time", 0)),
        input_priority=d.get("input_priority", "machine_order"),
        partial_delivery=bool(d.get("partial_delivery", True)),
        materials=materials,
        recipes=recipes,
        machines=_expand_machines(d["machines"]),
        orders=tuple(Order(**o) for o in orders.get("fixed") or []),
        random_orders=(
            RandomOrders(
                count_range=_int_range(rnd["count"]),
                products=tuple(rnd["products"]),
                quantity_range=_int_range(rnd["quantity"]),
                mix=rnd.get("mix", "even"),
                notice_range=_int_range(rnd["notice"]) if "notice" in rnd else None,
            )
            if rnd
            else None
        ),
    )


def _int_range(value) -> tuple[int, int]:
    """A YAML number or [low, high] list as a (low, high) pair; a single number n means (n, n)"""
    if isinstance(value, (list, tuple)):
        lo, hi = value
        return int(lo), int(hi)
    return int(value), int(value)


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
