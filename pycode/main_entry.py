from pycode.CFG import DEVICE_ID_AND_SPEC_DICT, RECIPE_NAME_AND_SPEC_DICT, INIT_RUNTIME_DEVICE_ID_AND_RECIPE_NAME_DICT
from pycode.factory_sim import FactorySim
from pycode.make_my_plots import draw_topology, plot_dashboard, plot_gantt


def main_entry():
    # --------------------------------------------------------------------------- #
    # 3.  Quick-and-dirty demo run                                               #
    # --------------------------------------------------------------------------- #
    sim_time = 300  # seconds
    print_every = 10  # seconds

    factory_sim = FactorySim(
        DEVICE_ID_AND_SPEC_DICT,
        RECIPE_NAME_AND_SPEC_DICT,
        INIT_RUNTIME_DEVICE_ID_AND_RECIPE_NAME_DICT,
    )
    # preload some raw materials
    factory_sim.add_stock("IronOre", 300)
    factory_sim.add_stock("Coal", 150)
    factory_sim.add_stock("IronBar", 40)
    factory_sim.add_stock("Screw", 300)

    for _ in range(sim_time):
        factory_sim.next_step()
        if factory_sim.clock % print_every == 0:
            print(factory_sim.snapshot())

    print("\n=== final summary ===")
    print(factory_sim.snapshot())

    draw_topology(factory_sim.device_id_and_obj_dict)
    plot_dashboard(factory_sim)
    plot_gantt(
        factory_sim,
        recipe_obj_list=factory_sim.recipe_name_and_obj_dict.values()
    )


if __name__ == '__main__':
    main_entry()
