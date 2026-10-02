"""Factory production simulation + reinforcement learning scheduling.

spec      scenario (fixed): materials, recipes, machines, money rules, orders
sim       state + the one-second step rule, no decisions
env       Gymnasium wrapper: observation encoding, action decoding, reward
policies  decision rules: keep, random, trained model
recorder  watches and records, exports Excel and charts
evaluate  runs whole episodes with a policy
training  checks the model on fixed test orders while it trains
web       interactive result pages: one per run, live training, all runs
"""

from sjfactory.env import FactoryEnv
from sjfactory.sim import STOP, FactorySim, State, StepReport
from sjfactory.spec import DEFAULT_SCENARIO, Scenario, load_scenario

__all__ = [
    "DEFAULT_SCENARIO",
    "STOP",
    "FactoryEnv",
    "FactorySim",
    "Scenario",
    "State",
    "StepReport",
    "load_scenario",
]
