from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Device:
    id: str
    category: str
    in_ch: int
    out_ch: int
    upstream: List[str]
    downstream: List[str]


@dataclass
class Recipe:
    name: str
    device_category: str  # what kind of device executes it
    cycle_time: int  # seconds per batch
    power_kw: float
    inputs: Dict[str, float]  # material → quantity / batch
    outputs: Dict[str, float]


@dataclass
class MaterialStock:
    name: str
    quantity: float


@dataclass
class Price:
    name: str
    price_buy: float | None
    price_sell: float | None
    storage_cost_per_time_unit: float | None


@dataclass
class Order:
    name: str
    quantity: float | None
    due_time: int | None

    def __lt__(self, other):
        return self.due_time < other.due_time

    def __eq__(self, other):
        return self.due_time == other.due_time

    def __le__(self, other):
        return self.due_time <= other.due_time


if __name__ == '__main__':
    pass
