# 铸造器 caster
# 构造器 constructor
# 组装器 assembler
# 产品制造器 manufacturer
DEVICE_SPEC = [
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