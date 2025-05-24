# 铸造器 caster
# 构造器 constructor
# 组装器 assembler
# 产品制造器 manufacturer
from pycode.utils import build_index_dict_by_id_from_list

DEVICE_SPEC_LIST = [
    # 没有固定上游（[]），意味着它直接吃外部原料。产物送往构造器。
    {
        "id": "CASTER-00",
        "category": "caster",  # 铸造器
        "in_ch": 1,
        "out_ch": 1,
        "upstream": [],
        "downstream": ["CONSTRUCTOR-01"],
    },
    {
        "id": "CASTER-01",
        "category": "caster",  # 铸造器
        "in_ch": 1,
        "out_ch": 1,
        "upstream": [],
        "downstream": ["CONSTRUCTOR-02"],
    },
    {
        "id": "CASTER-02",
        "category": "caster",  # 铸造器
        "in_ch": 2,
        "out_ch": 1,
        "upstream": [],
        "downstream": ["CONSTRUCTOR-03"],
    },
    {
        "id": "CASTER-03",
        "category": "caster",  # 铸造器
        "in_ch": 1,
        "out_ch": 1,
        "upstream": [],
        "downstream": ["CONSTRUCTOR-04"],  # 空闲
    },
    {
        "id": "CONSTRUCTOR-01",
        "category": "constructor",
        "in_ch": 1,
        "out_ch": 1,
        "upstream": ["CASTER-01"],
        "downstream": ["ASSEMBLER-01"],
    },
    {
        "id": "CONSTRUCTOR-02",
        "category": "constructor",
        "in_ch": 1,
        "out_ch": 1,
        "upstream": ["CASTER-02"],
        "downstream": ["ASSEMBLER-01"],
    },
    {
        "id": "CONSTRUCTOR-03",
        "category": "constructor",
        "in_ch": 1,
        "out_ch": 1,
        "upstream": ["CASTER-02"],
        "downstream": ["ASSEMBLER-02"],
    },
    {
        "id": "CONSTRUCTOR-04",
        "category": "constructor",
        "in_ch": 1,
        "out_ch": 1,
        "upstream": ["CASTER-02"],
        "downstream": ["ASSEMBLER-02"],
    },
    {
        "id": "ASSEMBLER-01",
        "category": "assembler",  # 组装器
        "in_ch": 2,
        "out_ch": 1,
        "upstream": ["CONSTRUCTOR-01", "CONSTRUCTOR-02"],
        "downstream": ["MANUFACTURER-01"],
    },
    {
        "id": "ASSEMBLER-02",
        "category": "assembler",  # 组装器
        "in_ch": 2,
        "out_ch": 1,
        "upstream": ["CONSTRUCTOR-01", "CONSTRUCTOR-02"],
        "downstream": ["MANUFACTURER-01"],
    },
    {
        "id": "MANUFACTURER-01",
        "category": "manufacturer",  # 产品制造器
        "in_ch": 2,
        "out_ch": 1,
        "upstream": ["ASSEMBLER-01"],
        "downstream": [],
    },
]


RECIPE_SPEC_LIST = [
    # ── T1：熔炼 ─────────────────────────────────────────
    {
        "name": "Cast_Iron",
        "device_category": "CASTER",
        "cycle_time": 60,
        "power_kw": 45.0,
        "inputs": {"IronOre": 30},
        "outputs": {"IronIngot": 30},
    },
    {
        "name": "Cast_Steel",
        "device_category": "CASTER",
        "cycle_time": 60,
        "power_kw": 50.0,
        "inputs": {"IronOre": 45, "Coal": 45},
        "outputs": {"SteelIngot": 45},
    },
    {
        "name": "Cast_Copper",
        "device_category": "CASTER",
        "cycle_time": 60,
        "power_kw": 50.0,
        "inputs": {"IronOre": 30, "Coal": 30},
        "outputs": {"CopperIngot": 30},
    },

    # ── T2：加工 ────────────────────────────────────────
    {
        "name": "Ingot_2_Bar",
        "device_category": "CONSTRUCTOR",
        "cycle_time": 60,
        "power_kw": 15.0,
        "inputs": {"IronIngot": 15},
        "outputs": {"IronBar": 15},
    },
    {
        "name": "Ingot_2_Screw",
        "device_category": "CONSTRUCTOR",
        "cycle_time": 12,
        "power_kw": 12.0,
        "inputs": {"IronIngot": 12.5},
        "outputs": {"Screw": 50},
    },

    # ── T3：装配 ────────────────────────────────────────
    {
        "name": "RotorAssemble",
        "device_category": "ASSEMBLER",
        "cycle_time": 20,
        "power_kw": 20.0,
        "inputs": {"IronBar": 4, "Screw": 100},
        "outputs": {"Rotor": 1},
    },

    # ── T4：总装 ────────────────────────────────────────
    {
        "name": "MotorFinal",
        "device_category": "MANUFACTURER",
        "cycle_time": 25,
        "power_kw": 30.0,
        "inputs": {"Rotor": 2},
        "outputs": {"Motor": 1},
    },
]

DEVICE_ID_AND_SPEC_DICT = build_index_dict_by_id_from_list(
    DEVICE_SPEC_LIST,
    "id",
)

RECIPE_NAME_AND_SPEC_DICT = build_index_dict_by_id_from_list(
    RECIPE_SPEC_LIST,
    "name",
)


INIT_RUNTIME_DEVICE_ID_AND_RECIPE_NAME_DICT = {
    "CASTER-01": "Cast_Iron",
    "CASTER-02": "Cast_Steel",
    "CASTER-03": "Cast_Copper",
    "CONSTRUCTOR-01": "Ingot_2_Bar",
    "CONSTRUCTOR-02": "Ingot_2_Screw",
    "ASSEMBLER-01": "RotorAssemble",
    "ASSEMBLER-02": "MotorFinal",
}
