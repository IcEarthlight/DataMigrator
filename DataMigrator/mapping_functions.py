from typing import Iterable
from datetime import datetime, timedelta


def datefix(date: float | datetime | None) -> str:
    if date is None:
        return ''
    
    if isinstance(date, float): #判断是否为浮点数，有时候读取的格式为235452.1123的浮点数模式
        base_date = datetime(1900, 1, 1)
        delta = timedelta(days = date - 1)
        date = base_date + delta
        fixeddata = date.strftime("%Y%m%d")
    else:
        fixeddata = datetime.strftime(date, "%Y%m%d")
    return fixeddata

