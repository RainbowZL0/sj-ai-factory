from pycode.CFG import (
    DEVICE_ID_AND_SPEC_DICT,
    RECIPE_NAME_AND_SPEC_DICT,
    INIT_RUNTIME_DEVICE_ID_AND_RECIPE_NAME_DICT, INIT_STOCK_NAME_AND_SPEC_DICT
)
from pycode.factory_sim import FactorySim
from pycode.make_my_plots import draw_device_topology, draw_dashboard, draw_gantt


def main_entry():
    # --------------------------------------------------------------------------- #
    # 3.  Quick-and-dirty demo run                                               #
    # --------------------------------------------------------------------------- #
    sim_time = 300  # seconds
    print_every = 10  # seconds

    factory_sim = FactorySim(
        device_id_and_spec_dict=DEVICE_ID_AND_SPEC_DICT,
        recipe_name_and_spec_dict=RECIPE_NAME_AND_SPEC_DICT,
        init_stock_name_and_spec_dict=INIT_STOCK_NAME_AND_SPEC_DICT,
        init_runtime_device_id_and_rcp_name_dict=INIT_RUNTIME_DEVICE_ID_AND_RECIPE_NAME_DICT,
        schedule_mode="greedy",
        dt=1,
    )
    # preload some raw materials
    # factory_sim.add_stock("IronOre", 300)
    # factory_sim.add_stock("Coal", 150)
    # factory_sim.add_stock("IronBar", 40)
    # factory_sim.add_stock("Screw", 300)

    for _ in range(sim_time):
        factory_sim.do_schedule_and_run_for_this_step(action_dict=None)
        if factory_sim.clock % print_every == 0:
            print(factory_sim.snapshot())

    print("\n=== final summary ===")
    print(factory_sim.snapshot())

    draw_device_topology(factory_sim.device_id_and_obj_dict)
    draw_dashboard(factory_sim)
    draw_gantt(
        factory_sim,
        recipe_obj_list=factory_sim.recipe_name_and_obj_dict.values()
    )


if __name__ == '__main__':
    main_entry()
