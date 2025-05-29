from typing import Literal

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableMultiInputActorCriticPolicy
from stable_baselines3.common.env_util import make_vec_env

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
from pycode.make_my_plots import draw_dashboard, draw_gantt, draw_device_topology
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
            manual_simulation_steps,
            **kwargs,
    ):
        """
        :param schedule_mode: 是否以调度方式启动。无调度意味着只要原料足够就开机运转。
        """
        super().__init__(**kwargs)

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
        self.simulation_steps = manual_simulation_steps

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

        """观测空间"""
        # 任意类的机器，最多的schedule选择数
        self.max_schedule_num = max(
            [
                len(i)
                for i in self.scheduler.dev_category_and_schedule_name_dict.values()
            ]
        )
        self.mat_num = len(init_stock_name_and_spec_dict)
        self.dev_num = len(self.device_id_and_spec_dict)
        self.price_num = len(init_price_name_and_spec_dict)
        self.visible_order_num = 50

        self.observation_space = self.get_observation_space()
        self.action_space = self.get_action_space()

        """factory_sim封装"""
        self.sim = self.get_init_factory_sim()

        """reset()次数记录"""
        self.reset_cnt = 0

    def get_observation_space(self):
        min_np_float32 = np.finfo(np.float32).min
        max_np_float32 = np.finfo(np.float32).max
        """
        order_name: ndarray int 离散值
        order_quantity: ndarray float
        order_due_time: ndarray float
        price_sell: ndarray float
        price_storage_cost_per_time_unit: ndarray float
        stock_quantity: ndarray float
        total_energy: 1d array float
        step_energy: 1d array float
        total_balance: 1d array float
        step_balance: 1d array float
        clock: 1d array float
        dev_state: 1d array float
        dev_bind_recipe: 1d array int 离散值
        """
        return spaces.Dict(
            {
                "order_name": spaces.MultiDiscrete(
                    [3] * self.visible_order_num,
                ),
                "order_quantity": spaces.Box(
                    low=0.0,
                    high=max_np_float32,
                    dtype=np.float32,
                    shape=(self.visible_order_num,)
                ),
                "order_due_time": spaces.Box(
                    low=-2.0,
                    high=max_np_float32,
                    dtype=np.float32,
                    shape=(self.visible_order_num,)
                ),
                "price_sell": spaces.Box(
                    low=0.0,
                    high=max_np_float32,
                    dtype=np.float32,
                    shape=(self.price_num,)
                ),
                "price_storage_cost_per_time_unit": spaces.Box(
                    low=0.0,
                    high=max_np_float32,
                    dtype=np.float32,
                    shape=(self.price_num,)
                ),
                # 库存量向量：非负浮点
                "stock_quantity": spaces.Box(
                    low=0.0,
                    high=max_np_float32,
                    shape=(self.mat_num,),
                    dtype=np.float32,
                ),
                # 标量指标
                "total_energy": spaces.Box(
                    0.0,
                    max_np_float32,
                    (1,),
                    np.float32
                ),
                "step_energy": spaces.Box(
                    0.0,
                    max_np_float32,
                    (1,),
                    np.float32
                ),
                # 每台设备的运行状态：IDLE=0, RUNNING=1
                "dev_state": spaces.MultiDiscrete(
                    [2] * self.dev_num
                ),
                "total_balance": spaces.Box(
                    min_np_float32,
                    max_np_float32,
                    (1,),
                    np.float32,
                ),
                "step_balance": spaces.Box(
                    min_np_float32,
                    max_np_float32,
                    (1,),
                    np.float32,
                ),
                "clock": spaces.Box(
                    0,
                    np.iinfo(np.int32).max,
                    (1,),
                    np.int32
                ),
                "dev_bind_recipe": spaces.MultiDiscrete(
                    [len(self.recipe_name_and_spec_dict)] * self.dev_num,
                )
            }
        )

    def get_observation_1(self):
        """
        传入
        "order_name", "order_quantity", "order_due_time",
        "price_name", "price_buy", "price_sell" ,"price_storage_cost_per_time_unit"
        "stock_name", "stock_quantity"
        "total_energy", "step_energy", "total_balance", "step_balance", "clock"
        "dev_id", "dev_state", "dev_bind_recipe"

        返回
        order_name: ndarray int
        order_quantity: ndarray float
        order_due_time: ndarray float
        price_sell: ndarray float
        price_storage_cost_per_time_unit: ndarray float
        stock_quantity: ndarray float
        total_energy: 1d array float
        step_energy: 1d array float
        total_balance: 1d array float
        step_balance: 1d array float
        clock: 1d array float
        dev_state: 1d array float
        dev_bind_recipe: 1d array int

        """
        d = self.get_obs_0()

        # 去掉无用字段
        """
        "order_name", "order_quantity", "order_due_time",
        "price_buy", "price_sell" ,"price_storage_cost_per_time_unit"
        "stock_quantity"
        "total_energy", "step_energy", "total_balance", "step_balance", "clock"
        "dev_state", "dev_bind_recipe"
        """
        d = {
            k: v for k, v in d.items()
            if k not in ["price_name", "stock_name", "dev_id", "price_buy"]  # TODO
        }

        # order 截取前20个
        cut_off = self.visible_order_num
        o_n = d["order_name"]
        o_q = d["order_quantity"]
        o_dt = d["order_due_time"]
        if len(o_n) > cut_off:
            d["order_name"] = o_n[:cut_off]
            d["order_quantity"] = o_q[:cut_off]
            d["order_due_time"] = o_dt[:cut_off]
        elif len(o_q) < cut_off:
            diffr = cut_off - len(o_n)
            d["order_name"] += [None] * diffr
            d["order_quantity"] += [0] * diffr
            d["order_due_time"] += [-1] * diffr

        temp = {"Motor": 0, "Frame": 1, None: 2}
        d["order_name"] = np.array([temp[i] for i in d["order_name"]], dtype=np.int64)

        # 所有能转为array的，price，order_q, order_due_time 和 stock_quantity
        array_list = ["order_quantity", "order_due_time", "price_buy", "price_sell",
                      "price_storage_cost_per_time_unit", "stock_quantity"]
        # 都是标量，转为一维numpy数组，"total_energy", "step_energy", "total_balance", "step_balance", "clock"
        scalar_float_list = ["total_energy", "step_energy", "total_balance", "step_balance"]
        scalar_int_list = ["clock"]
        for k, v in d.items():
            if k in array_list:
                d[k] = np.array(v, dtype=np.float32)
            if k in scalar_float_list:
                d[k] = np.array([v], dtype=np.float32)
            if k in scalar_int_list:
                d[k] = np.array([v], dtype=np.int32)

        # 转换dev_state
        d["dev_state"] = np.array(
            [
                0 if i is DevState.IDLE else 1
                for i in d["dev_state"]
            ],
            dtype=np.int32
        )

        temp_2 = {}
        for i, k in enumerate(self.recipe_name_and_obj_dict):
            temp_2[k] = i
        d["dev_bind_recipe"] = np.array(
            [temp_2[i] for i in d["dev_bind_recipe"]],
            dtype=np.int32
        )

        return d

    def get_obs_0(self):
        """
        "order_name", "order_quantity", "order_due_time",
        "price_name", "price_buy", "price_sell" ,"price_storage_cost_per_time_unit"
        "stock_name", "stock_quantity"
        "total_energy", "step_energy", "total_balance", "step_balance", "clock"
        "dev_id", "dev_state", "dev_bind_recipe"
        :return:
        """
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

    def get_init_factory_sim(self):
        return FactorySim(
            device_id_and_obj_dict=self.device_id_and_obj_dict,
            recipe_name_and_obj_dict=self.recipe_name_and_obj_dict,
            init_stock_name_and_spec_dict=self.init_stock_name_and_spec_dict,
            init_bind_of_device_id_and_rcp_name_dict=self.init_bind_of_device_id_and_rcp_name_dict,
            init_price_name_and_spec_dict=self.init_price_name_and_spec_dict,
            init_order_list=self.init_order_list,
            init_money=self.init_money,
            manual_simulation_steps=self.simulation_steps,
            dt=self.dt,
        )

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

        # 运行一步
        self.sim.high_level_step(self.scheduler)
        # 观测、奖励、终止标志、额外信息
        obs = self.get_observation_1()

        reward = obs["step_balance"].item()
        done = obs["clock"].item() >= self.simulation_steps  # 如果要模拟有限时任务，可以在这里判断
        truncated = False
        info = obs
        return obs, reward, done, truncated, info

    def reset(self, **kwargs):
        if self.reset_cnt > 0:
            draw_dashboard(self.sim.history_recorder)
            draw_gantt(
                self.sim.history_recorder,
                recipe_obj_list=self.recipe_name_and_obj_dict.values(),
            )
            for i in self.sim.price_mng.order_sell_result_mng.total_result:
                i.print_info()
            self.sim.history_recorder.save_to_excel()
            print("-------------------------------------\n")
        self.reset_cnt += 1

        super().reset()
        # 重新实例化模拟器，库存／时钟归零
        self.sim = self.get_init_factory_sim()
        return self.get_observation_1(), {}

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

            # TODO
            # choose %= len(possible_choice_list)

            assert choose < len(possible_choice_list)
            schedule_choice = possible_choice_list[choose]
            rst[dev_id] = schedule_choice
        return rst

    def get_my_action_mask(self):
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

    def action_masks(self):
        return self.get_my_action_mask()["action_mask"].flatten()


def get_fac_env():
    """制造一个RL用的factory_env"""
    return FactoryEnv(
        device_id_and_spec_dict=DEVICE_ID_AND_SPEC_DICT,
        recipe_name_and_spec_dict=RECIPE_NAME_AND_SPEC_DICT,
        init_stock_name_and_spec_dict=INIT_STOCK_NAME_AND_SPEC_DICT,
        init_bind_of_device_id_and_rcp_name_dict=INIT_BIND_OF_DEVICE_ID_AND_RECIPE_NAME_DICT,
        init_price_name_and_spec_dict=INIT_PRICE_NAME_AND_SPEC_DICT,
        init_order_list=INIT_ORDER_LIST,
        init_money=INIT_MONEY,
        schedule_mode="manual",
        dt=1,
        manual_simulation_steps=500
    )


def tst2():
    """RL方式跑"""
    vec_env = make_vec_env(get_fac_env, n_envs=3)  # DummyVecEnv or SubprocVecEnv
    model = MaskablePPO(
        MaskableMultiInputActorCriticPolicy,
        vec_env,
        learning_rate=3e-3,
        n_steps=2048,
        batch_size=256,
        gamma=0.95,
        verbose=1,
    )
    model.learn(total_timesteps=2_000_000, tb_log_name="runs/factory")


# def tst3():
#     from stable_baselines3.common.env_checker import check_env
#     check_env(get_fac_env(), warn=True)


def tst1():
    """greedy方式跑"""
    manual_simulation_steps = 5000
    fe = FactoryEnv(
        device_id_and_spec_dict=DEVICE_ID_AND_SPEC_DICT,
        recipe_name_and_spec_dict=RECIPE_NAME_AND_SPEC_DICT,
        init_stock_name_and_spec_dict=INIT_STOCK_NAME_AND_SPEC_DICT,
        init_bind_of_device_id_and_rcp_name_dict=INIT_BIND_OF_DEVICE_ID_AND_RECIPE_NAME_DICT,
        init_price_name_and_spec_dict=INIT_PRICE_NAME_AND_SPEC_DICT,
        init_order_list=INIT_ORDER_LIST,
        init_money=INIT_MONEY,
        schedule_mode="greedy",
        dt=1,
        manual_simulation_steps=manual_simulation_steps,
    )
    for _ in range(manual_simulation_steps):
        fe.greedy_schedule()
        fe.sim.high_level_step(fe.scheduler)

    draw_device_topology(fe.device_id_and_obj_dict)
    draw_dashboard(fe.sim.history_recorder)
    draw_gantt(
        fe.sim.history_recorder,
        recipe_obj_list=fe.recipe_name_and_obj_dict.values(),
    )


if __name__ == '__main__':
    tst2()
