"""平差输入的数据模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    """一条有向高差观测：height(to) - height(from_)。"""

    obs_id: str
    from_point: str
    to_point: str
    delta_h: float
    std_dev: float
    row: int


@dataclass(frozen=True)
class NetworkInput:
    observations: tuple[Observation, ...]
    controls: dict[str, float]
