"""levelnet 统一的错误类型。

所有输入校验失败都抛出 :class:`LevelNetError`，消息中注明出错位置
（文件名、CSV 行号或 JSON 路径），便于定位。
"""


class LevelNetError(Exception):
    """输入数据或平差过程中可诊断的错误。"""

