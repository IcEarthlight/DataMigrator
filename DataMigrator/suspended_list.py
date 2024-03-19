from __future__ import annotations

import re
from typing import NoReturn

from DataMigrator.database import Table, Database


class _SuspendInfo:
    def __init__(self,
                 conf: dict,
                 wait_for: list[list[str]],
                 index: int,
                 rel_f: function
        ) -> None:

        for dpd in wait_for:
            if re.match(r"_This\..+", dpd[0]):
                break
        else:
            print(f"{index} -> {wait_for}")
            raise Exception(f"DependencyError")
        
        self.conf: dict = conf
        self.wait_for: list[list[str]] = wait_for
        self.index: int = index
        self.released: bool = False
        self.release_func: function = rel_f
    
    def release(self) -> None:
        self.release_func(self.conf, self.index)
        self.released = True


class SuspendedList:
    def __init__(self, rel_f: function) -> None:
        self.waitlist: dict[tuple[str], list[_SuspendInfo]] = {}
        self.release_function: function = rel_f
    
    def append(self, conf: dict, wait_for: list[list[str]], index: int) -> None:
        new_info: _SuspendInfo = _SuspendInfo(conf, wait_for, index, self.release_function)

        wf: list[str]
        for wf in self.waitlist:
            if tuple(wf) in self.waitlist:
                self.waitlist[tuple(wf)].append(new_info)
            else:
                self.waitlist[tuple(wf)] = [new_info]
    
    def something_here(self) -> bool:
        return bool(self.waitlist)
    
    def check(self, new_col_name: list[str]) -> None:
        new_col_name: tuple[str] = tuple(new_col_name)

        if new_col_name in self.waitlist:
            for sus_info in self.waitlist[new_col_name]:
                if not sus_info.released:
                    sus_info.release()
            del self.waitlist[new_col_name]
    
    def raise_exception(self, table_name: str) -> NoReturn:
        sus_confs: list[_SuspendInfo]
        for _, sus_confs in zip(self.waitlist):
            for sc in sus_confs:
                print(f"{table_name} {sc.conf["title"]} {sc.index} -> {sc.wait_for}")
        raise Exception("DependencyError")
