from collections import defaultdict
import pandas as pd


class HistoryRecorder:
    """
    统一收集所有随时间变动的标量 / 向量数据。
    · 标量: 余额、累计能耗等 —— 存到 self.scalar_logs[name] -> list
    · 向量: 库存、设备状态等 —— 存到 self.vector_logs[group][key] -> list
    """

    def __init__(self):
        self.step_counter = 0
        # {metric: [v0,v1,...]}
        self.scalar_logs = defaultdict(list)
        # {group: {key: [v0,v1]}}
        self.vector_logs = defaultdict(lambda: defaultdict(list))

    # ---------- 写入接口 ----------
    def log_scalar(self, name, value):
        self.scalar_logs[name].append(value)

    def log_vector(self, group, key, value):
        self.vector_logs[group][key].append(value)

    def next_step(self):
        self.step_counter += 1

    # ---------- 读取接口 ----------
    def get_scalar(self, name):
        return self.scalar_logs[name]

    def get_vector(self, group, key):
        return self.vector_logs[group][key]

    def to_dataframe(self):
        """把全量标量指标拼成 DataFrame，便于外部分析"""
        return pd.DataFrame(self.scalar_logs)
