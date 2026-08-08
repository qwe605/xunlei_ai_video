import os
import re


MAGNET_PATTERN = re.compile(
    r"^magnet:\?xt=urn:btih:(?:[A-Fa-f0-9]{40}|[A-Za-z2-7]{32})(?:&[^\r\n]{1,4000})?$"
)


class MagnetOpenError(Exception):
    pass


def open_magnet_in_system(value: str) -> None:
    magnet = value.strip()
    if not MAGNET_PATTERN.fullmatch(magnet):
        raise MagnetOpenError("磁力链接格式不正确")
    if os.name != "nt":
        raise MagnetOpenError("当前系统不支持调用迅雷协议")
    try:
        os.startfile(magnet)  # type: ignore[attr-defined]
    except OSError as error:
        raise MagnetOpenError("没有找到可处理磁力链接的迅雷客户端") from error
