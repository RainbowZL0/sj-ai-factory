from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict

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

    def can_start(self, stock: Dict[str, int]) -> bool:
        """Check if enough inputs exist to launch a batch."""
        return all(stock[m] >= q for m, q in self.recipe.inputs.items())

    def start_batch(self, stock: Dict[str, int]):
        # 开始一次生产
        for m, q in self.recipe.inputs.items():
            stock[m] -= q
        self.state = DevState.RUNNING
        self.t_left = self.recipe.cycle_time

    def tick(self, stock: Dict[str, int]):
        if self.state is DevState.RUNNING:
            self.t_left -= 1
            if self.t_left == 0:
                # finish outputs
                for m, q in self.recipe.outputs.items():
                    stock[m] += q
                self.state = DevState.FINISHED
        elif self.state is DevState.FINISHED:
            self.state = DevState.IDLE  # ready for next batch
