from collections import defaultdict
from typing import Tuple, Dict, Any
from pycode.factory_sim import FactorySim


class FactoryEnv:
    def __init__(self,
                 device_specs: dict,
                 recipe_specs: dict,
                 init_bind: dict,
                 dt):
        self.sim = FactorySim(
            device_specs,
            recipe_specs,
            init_bind,
            dt=dt
        )
        self.dt = dt

    def reset(self) -> Dict[str, Any]:
        # 重新实例化模拟器，库存／时钟归零
        self.sim = FactorySim(
            self.sim.device_id_and_spec_dict,
            self.sim.recipe_name_and_spec_dict,
            self.sim.runtime_device_id_and_rcp_name_dict,
            dt=self.dt
        )
        # 可以预加载原料
        # self.sim.add_stock(...)
        return self._get_observation()

    def step(self, action: Dict[str, str | None]) -> Tuple[Dict, float, bool, dict]:
        # 1) 应用动作
        self.sim.apply_actions(action)
        # 2) 推进 dt 秒
        self.sim.run_one_step_after_schedule()
        # 3) 观测、奖励、终止标志、额外信息
        obs = self._get_observation()
        reward = 0.0  # 先占位，后面再接成本／收益模型
        done = False  # 如果要模拟有限时任务，可以在这里判断
        info = {}
        return obs, reward, done, info

    def _get_observation(self) -> Dict[str, Any]:
        return {
            "time": self.sim.clock,
            "stock": dict(self.sim.stock),
            "device_state": {d: rt.state.name
                             for d, rt in self.sim.dev_id_and_dev_runtime_dict.items()},
            "current_recipe": {d: rt.recipe.name
                               for d, rt in self.sim.dev_id_and_dev_runtime_dict.items()},
        }
