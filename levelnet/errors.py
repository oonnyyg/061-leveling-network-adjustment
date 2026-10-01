"""平差过程中的错误类型。"""


class LevelNetError(Exception):
    """输入数据或数值计算错误基类。"""


class InputError(LevelNetError):
    """输入文件内容不合法，message 中注明出错位置。"""
