from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _converter():
    from opencc import OpenCC

    return OpenCC("t2s")


MAINLAND_TERMS = {
    "影片": "视频",
    "资讯": "信息",
    "软体": "软件",
    "网路": "网络",
    "程式": "程序",
    "资料库": "数据库",
    "伺服器": "服务器",
    "登入": "登录",
    "帐号": "账号",
    "档案": "文件",
}


def to_simplified_chinese(value: str) -> str:
    """统一模型输出，并把高频港台产品用语替换为大陆用户熟悉的表达。"""
    normalized = _converter().convert(value)
    for source, target in MAINLAND_TERMS.items():
        normalized = normalized.replace(source, target)
    normalized = (
        normalized.replace(",", "，")
        .replace(";", "；")
        .replace("?", "？")
        .replace("!", "！")
    )
    return normalized


def simplify_data(value: Any) -> Any:
    """递归清洗模型 JSON 中的字符串，字段名和非文本值保持不变。"""
    if isinstance(value, str):
        return to_simplified_chinese(value)
    if isinstance(value, list):
        return [simplify_data(item) for item in value]
    if isinstance(value, dict):
        return {key: simplify_data(item) for key, item in value.items()}
    return value
