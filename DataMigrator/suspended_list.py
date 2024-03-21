from __future__ import annotations

import re
from typing import NoReturn

from DataMigrator.database import Table, Database

ColInfo = tuple[str, str]

class _SuspendInfo:
    def __init__(self,
                 conf: dict,
                 this_sheet_name: str,
                 wait_for: list[list[str] | ColInfo],
                 index: int,
                 rel_f: function
        ) -> None:
        self.conf: dict = conf
        self.wait_for: list[ColInfo] = []
        self.index: int = index
        self.released: bool = False
        self.release_func: function = rel_f

        for i in range(len(wait_for)):
            if m := re.match(r"(_This\.)(.+)", wait_for[i][0]):
                self.wait_for.append((m.group(2), wait_for[i][1]))
        
        if not self.wait_for:
            print(f"{index} -> {wait_for}")
            raise Exception(f"DependencyError")
        
    def release(self) -> None:
        self.release_func(self.conf, self.index)
        self.released = True


class SuspendedList:
    def __init__(self, rel_f: function) -> None:
        self.waitlist: dict[ColInfo, list[_SuspendInfo]] = {}
        self.release_function: function = rel_f
    
    def append(self,
               conf: dict,
               this_sheet_name: str,
               wait_for: list[list[str]], index: int) -> None:
        new_info: _SuspendInfo = _SuspendInfo(conf,
                                              this_sheet_name,
                                              wait_for, index,
                                              self.release_function)

        wf: list[str]
        for wf in new_info.wait_for:
            if tuple(wf) in self.waitlist:
                self.waitlist[tuple(wf)].append(new_info)
                return
            else:
                self.waitlist[tuple(wf)] = [new_info]
    
    def something_here(self) -> bool:
        return bool(self.waitlist)
    
    def check(self, new_col_info: ColInfo) -> None:

        if new_col_info in self.waitlist:
            for sus_info in self.waitlist[new_col_info]:
                sus_info.wait_for.remove(new_col_info)
                if not sus_info.released and not sus_info.wait_for:
                    # print(f"release {sus_info.conf = } {sus_info.index = }")
                    sus_info.release()
            del self.waitlist[new_col_info]
    
    def raise_exception(self, table_name: str) -> NoReturn:
        sus_confs: list[_SuspendInfo]
        for _, sus_confs in self.waitlist.items():
            for sc in sus_confs:
                print(f"{table_name} {sc.conf["title"]} {sc.index} -> {sc.wait_for}")
        raise Exception("DependencyError")
