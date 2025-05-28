from dataclasses import dataclass
from enum import Enum, auto

from pycode.StockManagerRuntime import StockManagerRuntime
from pycode.data_class import Device, Recipe


class DevState(Enum):
    IDLE = auto()
    RUNNING = auto()
    # OFF = auto()


@dataclass
class DevRuntime:
    device: Device
    bind_recipe: Recipe
    state: DevState = DevState.IDLE
    t_left: int = 0  # seconds remaining for current batch

    def can_start(self, runtime_stock_manager: StockManagerRuntime) -> bool:
        """Check if enough inputs exist to launch a batch."""
        # 如果正在干活，还没结束，则不能开始下一个任务
        if self.state is DevState.RUNNING:
            return False
        # 如果所需材料库存不够，也不能开始生产
        for material, need_quantity in self.bind_recipe.inputs.items():
            if runtime_stock_manager.get_obj_by_name(material).quantity < need_quantity:
                return False
        # 其他情况，判断可以开始生产
        return True

    def start_batch(self, runtime_stock_manager: StockManagerRuntime):
        # 标记一次生产开始，消耗库存开始生产
        for m, q in self.bind_recipe.inputs.items():
            runtime_stock_manager.get_obj_by_name(m).quantity -= q
        self.state = DevState.RUNNING
        self.t_left = self.bind_recipe.cycle_time

    def tick(self, runtime_stock_manager: StockManagerRuntime, dt: int):
        """推进 dt 秒；若生产结束（t_left≤0），产出并切到 FINISHED。"""
        if self.state is DevState.RUNNING:
            self.t_left -= dt
            if self.t_left <= 0:
                for material, produce_quantity in self.bind_recipe.outputs.items():
                    runtime_stock_manager.get_obj_by_name(material).quantity += produce_quantity
                self.state = DevState.IDLE
