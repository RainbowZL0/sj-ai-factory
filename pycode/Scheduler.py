import copy
import random

from pycode.dev_runtime import DevState


class Scheduler:
    def __init__(
        self,
        schedule_mode,
        bind_of_device_id_and_rcp_name_dict: dict | None,
        dev_category_and_rcp_name_dict,
    ):
        self.schedule_mode = schedule_mode
        # 以bind_of_device_id_and_rcp_name_dict，生成schedule的模板
        self.schedule_plan: dict | None = bind_of_device_id_and_rcp_name_dict
        self.runtime_bind_of_device_id_and_rcp_name_dict = copy.copy(
            bind_of_device_id_and_rcp_name_dict
        )
        self.dev_category_and_schedule_name_dict = get_dev_category_and_schedule_name_dict(
            dev_category_and_rcp_name_dict=dev_category_and_rcp_name_dict
        )

        self.tst_cnt = 0

    def get_schedule_choice_list_by_category(self, cat):
        return self.dev_category_and_schedule_name_dict[cat]

    def apply_plan_to_runtime(
            self,
            dev_id_and_dev_runtime_dict,
            recipe_name_and_obj_dict,
    ):
        """决定本次step的所有设备的状态
        action_dict: {device_id: recipe_name 或 None}, None表示这台机器维持原先的调度不作调整
        只有当设备处于 IDLE 且 action 指定了合法配方，才切换它的 recipe 属性。
        """
        assert self.schedule_plan is not None
        # TODO
        # self.random_change_schedule_tst(
        #     dev_id_and_dev_runtime_dict=dev_id_and_dev_runtime_dict,
        # )
        for dev_id, dev_schedule in self.schedule_plan.items():
            dev_rt = dev_id_and_dev_runtime_dict.get(dev_id)
            if dev_schedule is None:  # None代表无需更改调度，维持原状
                continue

            # 如果还在生产上一个配方，则不能更改调度。直接报错，说明上一步生成的plan有误，去检查代码。
            if dev_rt.state is not DevState.IDLE:
                raise ValueError
            # 检查这台设备类别允许做该配方。直接报错，说明上一步生成的plan有误，去检查代码。
            dev_category = dev_rt.device.category
            if dev_schedule not in self.dev_category_and_schedule_name_dict[dev_category]:
                raise ValueError(
                    f"{dev_id}({dev_category}) 不支持配方 {dev_schedule}"
                )

            # 切到新plan，但不修改设备运行状态，由之后的tick()做
            # 因为是否能实际运行该配方，还取决于需求的材料是否有足够库存，这一点将由tick()检查
            dev_rt.bind_recipe = recipe_name_and_obj_dict[
                dev_schedule
            ]  # 修改dev runtime的recipe属性
            self.runtime_bind_of_device_id_and_rcp_name_dict[dev_id] = dev_schedule

    def change_schedule_plan(self, schedule_plan):
        self.schedule_plan = schedule_plan

    def random_change_schedule_tst(
            self,
            dev_id_and_dev_runtime_dict,
    ):
        """
        {'ASSEMBLER-01': 'RotorAssemble', 'ASSEMBLER-02': 'RotorAssemble', 'ASSEMBLER-03': 'StatorAssemble',
        'ASSEMBLER-04': 'StatorAssemble', 'ASSEMBLER-05': 'MotorFinal', 'CASTER-01': 'Cast_Iron', 'CASTER-02':
        'Cast_Iron', 'CASTER-03': 'Cast_Iron', 'CASTER-04': 'Cast_Steel', 'CASTER-05': 'Cast_Steel', 'CASTER-06':
        'Cast_Copper', 'CONSTRUCTOR-01': 'Ingot_2_Bar', 'CONSTRUCTOR-02': 'Ingot_2_Bar', 'CONSTRUCTOR-03': 'Ingot_2_Bar',
        'CONSTRUCTOR-04': 'Ingot_2_Bar', 'CONSTRUCTOR-05': 'Ingot_2_Bar', 'CONSTRUCTOR-06': 'Ingot_2_Bar',
        'CONSTRUCTOR-07': 'Bar_2_Screw', 'CONSTRUCTOR-08': 'Bar_2_Screw', 'CONSTRUCTOR-09': 'Bar_2_Screw',
        'CONSTRUCTOR-10': 'Bar_2_Screw', 'CONSTRUCTOR-11': 'Ingot_2_Tube', 'CONSTRUCTOR-12': 'Ingot_2_Tube',
        'CONSTRUCTOR-13': 'Ingot_2_Wire', 'CONSTRUCTOR-14': 'Ingot_2_Wire'}
        :param dev_id_and_dev_runtime_dict:
        :return:
        """
        if self.tst_cnt % 50 == 0:
            for dev_id, dev_schedule in self.schedule_plan.items():
                dev_category = dev_id_and_dev_runtime_dict[dev_id].device.category
                schedule_choices = self.dev_category_and_schedule_name_dict[dev_category]
                self.schedule_plan[dev_id] = random.choice(schedule_choices)
        self.tst_cnt += 1


def get_dev_category_and_schedule_name_dict(dev_category_and_rcp_name_dict):
    rst = copy.deepcopy(dev_category_and_rcp_name_dict)
    for dev_cat in rst:
        l: list = rst[dev_cat]
        l.insert(0, None)
    return rst
