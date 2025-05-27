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


@dataclass(frozen=True)
class Recipe:
    name: str
    device_category: str  # what kind of device executes it
    cycle_time: int  # seconds per batch
    power_kw: float
    inputs: Dict[str, float]  # material → quantity / batch
    outputs: Dict[str, float]


@dataclass
class Material:
    name: str
    quantity: float
    price_buy: float
    price_sell: float
    storage_cost_per_time_unit: float
    can_buy: bool
    can_sell: bool
