from typing import Literal

import gymnasium as gym
import numpy as np

from pycode.CFG import (
    DEVICE_ID_AND_SPEC_DICT,
    RECIPE_NAME_AND_SPEC_DICT,
    INIT_BIND_OF_DEVICE_ID_AND_RECIPE_NAME_DICT,
    INIT_STOCK_NAME_AND_SPEC_DICT,
    INIT_PRICE_NAME_AND_SPEC_DICT,
    INIT_ORDER_LIST,
    INIT_MONEY
)
from pycode.Scheduler import Scheduler
from pycode.data_class import Device
from pycode.dev_runtime import DevState, DevRuntime
from pycode.factory_sim import FactorySim
from pycode.make_my_plots import draw_device_topology, draw_dashboard, draw_gantt
from pycode.utils import (
    build_dict_of_dev_category_and_recipe_name,
    build_dict_of_recipe_name_and_obj,
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
        """
        :param schedule_mode: 是否以调度方式启动。无调度意味着只要原料足够就开机运转。
        """
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
        # 字典，设备id -> 设备obj
        self.device_id_and_obj_dict = {
            dev_id: Device(**dev_dict)
            for dev_id, dev_dict in device_id_and_spec_dict.items()
        }
        # 字典，配方名 -> 配方obj
        self.recipe_name_and_obj_dict = build_dict_of_recipe_name_and_obj(
            recipe_name_and_spec_dict=recipe_name_and_spec_dict,
            whether_convert_to_one_second_of_cycle_time=False,
        )
        # 字典，设备类别名 -> 能做哪些配方名的list，这里不包括None。有None的版本由Scheduler负责生成。
        dev_category_and_rcp_name_dict = build_dict_of_dev_category_and_recipe_name(
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
        )

        # Scheduler调度器
        self.scheduler = Scheduler(
            schedule_mode=schedule_mode,
            bind_of_device_id_and_rcp_name_dict=init_bind_of_device_id_and_rcp_name_dict,
            dev_category_and_rcp_name_dict=dev_category_and_rcp_name_dict,
        )

        self.dev_num = len(self.device_id_and_spec_dict)
        # 任意类的机器，最多的schedule选择数
        self.max_schedule_num = max(
            [
                len(i)
                for i in self.scheduler.dev_category_and_schedule_name_dict.values()
            ]
        )

        """factory_sim封装"""
        self.sim = self.get_init_factory_sim()

    def get_init_factory_sim(self):
        return FactorySim(
            device_id_and_obj_dict=self.device_id_and_obj_dict,
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
            init_stock_name_and_spec_dict=self.init_stock_name_and_spec_dict,
            init_bind_of_device_id_and_rcp_name_dict=self.init_bind_of_device_id_and_rcp_name_dict,
            init_price_name_and_spec_dict=self.init_price_name_and_spec_dict,
            init_order_list=self.init_order_list,
            init_money=self.init_money,
            dt=self.dt,
        )

    def reset(self, **kwargs):
        # 重新实例化模拟器，库存／时钟归零
        self.sim = self.get_init_factory_sim()
        return self.get_observation()

    def step(self, action):
        """
        :param action: ndarray, [1, 3, 4, 0, ...], 一维数组表示每个机器的调度选择
        """
        # 应用动作
        action_dict = self.get_action_dict_from_ndarray(action_array=action)
        self.scheduler.change_schedule_plan(schedule_plan=action_dict)
        self.scheduler.apply_plan_to_runtime(
            dev_id_and_dev_runtime_dict=self.sim.dev_id_and_dev_runtime_dict,
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
        )

        # TODO
        # 运行一步
        self.sim.high_level_step()
        # 观测、奖励、终止标志、额外信息
        obs = self.get_observation()

        reward = 0.0  # 先占位，后面再接成本／收益模型
        done = False  # 如果要模拟有限时任务，可以在这里判断
        info = {}
        return obs, reward, done, info

    def greedy_schedule(self):
        schedule_plan = {}
        for dev_id, dev_rt in self.sim.dev_id_and_dev_runtime_dict.items():
            if dev_rt.state is DevState.IDLE:
                # 从初始化 yaml 读入的绑定表里拿默认配方
                schedule_plan[dev_id] = self.init_bind_of_device_id_and_rcp_name_dict[dev_id]
            else:
                schedule_plan[dev_id] = None
        self.scheduler.change_schedule_plan(schedule_plan=schedule_plan)
        self.scheduler.apply_plan_to_runtime(
            dev_id_and_dev_runtime_dict=self.sim.dev_id_and_dev_runtime_dict,
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
        )

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

    def get_action_dict_from_ndarray(self, action_array):
        """
        :param action_array: ndarray, [1, 3, 4, 0, ...], 一维数组表示每个机器的调度选择
        """
        rst = {}
        for i, dev_id in enumerate(self.device_id_and_spec_dict):
            dev_cat = self.device_id_and_obj_dict[dev_id].category
            possible_choice_list = self.scheduler.get_schedule_choice_list_by_category(dev_cat)
            choose = action_array[i]
            assert choose < len(possible_choice_list)
            schedule_choice = possible_choice_list[action_array[i]]
            rst[dev_id] = schedule_choice
        return rst

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
                    self.scheduler.get_schedule_choice_list_by_category(dev_rt.device.category)
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
        schedule_mode="greedy",
        dt=1,
    )

    print_every = 1
    sim_time = 1500

    for _ in range(sim_time):
        f_e.greedy_schedule()
        f_e.sim.high_level_step(f_e.scheduler)

        if f_e.sim.clock % print_every == 0:
            print(f_e.sim.snapshot())

    print("\n=== final summary ===")
    print(f_e.sim.snapshot())

    draw_device_topology(f_e.device_id_and_obj_dict)
    draw_dashboard(f_e.sim.history_recorder)
    draw_gantt(
        f_e.sim.history_recorder,
        recipe_obj_list=f_e.recipe_name_and_obj_dict.values(),
    )


if __name__ == '__main__':
    tst1()
