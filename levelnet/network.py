"""无向连通分量分析。"""

from .errors import InputError
from .models import NetworkInput


def check_components(net: NetworkInput) -> None:
    """每个无向连通分量至少含一个控制点, 否则报错。"""
    adjacency: dict[str, set[str]] = {}
    for obs in net.observations:
        adjacency.setdefault(obs.from_point, set()).add(obs.to_point)
        adjacency.setdefault(obs.to_point, set()).add(obs.from_point)

    visited: set[str] = set()
    for start in sorted(adjacency):
        if start in visited:
            continue
        stack = [start]
        component: list[str] = []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            stack.extend(adjacency[node])
        if not any(name in net.controls for name in component):
            raise InputError(
                "存在不含控制点的无向连通分量, 无法确定高程基准; "
                f"该分量包含点位: {', '.join(sorted(component))}"
            )
