from dataclasses import dataclass
from enum import Enum, auto

from pycode.StockManagerRuntime import StockManagerRuntime
from pycode.data_class import Device, Recipe


class DevState(Enum):
    IDLE = auto()
    RUNNING = auto()
    FINISHED = auto()


@dataclass
class DevRuntime:
    device: Device
    recipe: Recipe
    state: DevState = DevState.IDLE
    t_left: int = 0  # seconds remaining for current batch

    def can_start(self, runtime_stock_manager: StockManagerRuntime) -> bool:
        """Check if enough inputs exist to launch a batch."""
        for material, need_quantity in self.recipe.inputs.items():
            if runtime_stock_manager.get_obj_by_name(material).quantity < need_quantity:
                return False
        return True

    def start_batch(self, runtime_stock_manager: StockManagerRuntime):
        # 开始一次生产
        for m, q in self.recipe.inputs.items():
            runtime_stock_manager.get_obj_by_name(m).quantity -= q
        self.state = DevState.RUNNING
        self.t_left = self.recipe.cycle_time

    def tick(self, runtime_stock_manager: StockManagerRuntime, dt: int):
        """推进 dt 秒；若生产结束（t_left≤0），产出并切到 FINISHED。"""
        if self.state is DevState.RUNNING:
            self.t_left -= dt
            if self.t_left <= 0:
                for material, produce_quantity in self.recipe.outputs.items():
                    runtime_stock_manager.get_obj_by_name(material).quantity += produce_quantity
                self.state = DevState.FINISHED
        elif self.state is DevState.FINISHED:
            self.state = DevState.IDLE
