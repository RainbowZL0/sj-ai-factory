from typing import Literal

import gymnasium as gym
import numpy as np

from pycode.dev_runtime import DevState, DevRuntime
from pycode.factory_sim import FactorySim

from pycode.CFG import (
    DEVICE_ID_AND_SPEC_DICT,
    RECIPE_NAME_AND_SPEC_DICT,
    INIT_BIND_OF_DEVICE_ID_AND_RECIPE_NAME_DICT,
    INIT_STOCK_NAME_AND_SPEC_DICT,
    INIT_PRICE_NAME_AND_SPEC_DICT,
    INIT_ORDER_LIST,
    INIT_MONEY
)


class FactoryEnv(gym.Env):
    def __init__(
            self,
            device_id_and_spec_dict,
            recipe_name_and_spec_dict,
            init_stock_name_and_spec_dict,
            init_bind_of_device_id_and_rcp_name_dict,
            init_price_name_and_spec_dict,
            init_order_list,
            init_money,
            schedule_mode: Literal["greedy", "manual"],
            dt,
    ):
        """传入属性"""
        self.device_id_and_spec_dict = device_id_and_spec_dict
        self.recipe_name_and_spec_dict = recipe_name_and_spec_dict
        self.init_stock_name_and_spec_dict = init_stock_name_and_spec_dict
        self.init_bind_of_device_id_and_rcp_name_dict = init_bind_of_device_id_and_rcp_name_dict
        self.init_price_name_and_spec_dict = init_price_name_and_spec_dict
        self.init_order_list = init_order_list
        self.init_money = init_money
        self.schedule_mode = schedule_mode
        self.dt = dt

        """新属性"""
        self.sim = self.get_init_factory_sim()

        self.dev_num = len(self.device_id_and_spec_dict)
        # 任意类的机器，最多的schedule选择数
        self.max_schedule_num = max(
            [
                len(i)
                for i in self.sim.scheduler.dev_category_and_schedule_name_dict.values()
            ]
        )

    def get_init_factory_sim(self):
        return FactorySim(
            device_id_and_spec_dict=self.device_id_and_spec_dict,
            recipe_name_and_spec_dict=self.recipe_name_and_spec_dict,
            init_stock_name_and_spec_dict=self.init_stock_name_and_spec_dict,
            init_bind_of_device_id_and_rcp_name_dict=self.init_bind_of_device_id_and_rcp_name_dict,
            init_price_name_and_spec_dict=self.init_price_name_and_spec_dict,
            init_order_list=self.init_order_list,
            init_money=self.init_money,
            schedule_mode=self.schedule_mode,
            dt=self.dt,
        )

    def reset(self):
        # 重新实例化模拟器，库存／时钟归零
        self.sim = self.get_init_factory_sim()
        return self.get_observation()

    def step(self):
        # 应用动作
        self.sim.scheduler.do_schedule()
        # 运行一步
        self.sim.high_level_step()
        # 观测、奖励、终止标志、额外信息
        obs = self.get_observation()

        reward = 0.0  # 先占位，后面再接成本／收益模型
        done = False  # 如果要模拟有限时任务，可以在这里判断
        info = {}
        return obs, reward, done, info

    def get_observation(self):
        order_env = self.sim.order_mng.get_env_status()
        price_env = self.sim.price_mng.get_env_status()
        stock_env = self.sim.stock_mng.get_env_status()
        dev_and_other_env = self.sim.get_env_status()

        total_env = {
            **order_env,
            **price_env,
            **stock_env,
            **dev_and_other_env,
        }
        return total_env

    def get_action_space(self):
        return gym.spaces.MultiDiscrete(
            [self.max_schedule_num] * self.dev_num  # 例子，[5, 3] 表示首个机器能选0~4总共5种状态，第二个能选3种
        )

    def get_action_mask(self):
        mask = np.zeros(
            shape=(
                self.dev_num,
                self.max_schedule_num,
            ),
            dtype=bool
        )

        for i, dev_id in enumerate(self.device_id_and_spec_dict.keys()):
            dev_rt = self.sim.dev_id_and_dev_runtime_dict[dev_id]
            dev_rt: DevRuntime
            # index 0 总是合法（保持原配方）
            mask[i, 0] = True

            # 只有机器空闲时才允许切配方
            if dev_rt.state is DevState.IDLE:
                # 根据机器的类型找它能做前几个配方，把对应的位置填成True
                schedule_choice_num = len(
                    self.sim.scheduler.get_schedule_choice_list_by_category(dev_rt.device.category)
                )
                mask[i, 1: schedule_choice_num] = True
        return {"action_mask": mask}


def tst1():
    f_e = FactoryEnv(
        device_id_and_spec_dict=DEVICE_ID_AND_SPEC_DICT,
        recipe_name_and_spec_dict=RECIPE_NAME_AND_SPEC_DICT,
        init_stock_name_and_spec_dict=INIT_STOCK_NAME_AND_SPEC_DICT,
        init_bind_of_device_id_and_rcp_name_dict=INIT_BIND_OF_DEVICE_ID_AND_RECIPE_NAME_DICT,
        init_price_name_and_spec_dict=INIT_PRICE_NAME_AND_SPEC_DICT,
        init_order_list=INIT_ORDER_LIST,
        init_money=INIT_MONEY,
        schedule_mode="manual",
        dt=1,
    )
    a = f_e.get_action_mask()
    b = f_e.get_action_space()
    print(a)
    print(b)


if __name__ == '__main__':
    tst1()
