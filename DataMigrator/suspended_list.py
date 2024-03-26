from __future__ import annotations

import re
from typing import NoReturn

from DataMigrator.database import Table, Database

ColInfo = tuple[str, str]
# (Sheetname, Columntitle)

class _SuspendInfo:
    """ A class that stores the information of one single suspended column.

        # Attributes
        - conf: the config data in a dict
        - wait_for: what is the column waiting for
        - index: where should the column be in the table
        - released: if this column is released from the waitlist
        - released_func: called when released

        # Methods
        - release
    """
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
            raise Exception(f"DependencyError:\n{conf["title"]} {index} -> {wait_for}")
        
    def release(self) -> None:
        self.release_func(self.conf, self.index)
        self.released = True


class SuspendedList:
    """ A Class that can temporarily store config information of columns that requires data
        not been read and cannot be processed yet. Every time when a new column finishes
        processing, the check() method would be called to check if this is a column that is
        needed by a column on the waitlist. Once all required columns are available for a
        column on the waitlist, this columns would be released from the waitlist and been
        properly processed.

        # Attributes
        - waitlist: A dict with the structure of {(Sheetname, Columntitle): [info1, info2,
        ...]} In each key-value pair, the value is a bunch of column infos that is waiting
        for the key, which is a tuple reqresents an unloaded column.
        - release_function: The function that would be called when a column info is released
        from the waitlist.

        # Methods
        - append: add a new column to the waitlist
        - check: check if any column can be released now and remove from the waitlist
        - something_here: check if there is anything left in the waitlist
        - raise_exception

        # Raises
        When the all other columns are completed, but some columns are still waiting for
        a columns that is not exsists, an exception would be raised through calling the method
        raise_exception()
    """
    def __init__(self, rel_f: function) -> None:
        self.waitlist: dict[ColInfo, list[_SuspendInfo]] = {}
        self.release_function: function = rel_f
    
    def append(self,
               conf: dict,
               this_sheet_name: str,
               wait_for: list[list[str]], index: int) -> None:
        """ Add a new column to the waitlist, providing the config data, the sheet name of the
            column, and most importantly, what is the column waiting for.
        """
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
    
    def check(self, new_col_info: ColInfo) -> None:
        """ Given the information of a new added column (Sheetname, Columntitle), check if any
            column can be released now and remove from the waitlist.
        """
        if new_col_info in self.waitlist:
            for sus_info in self.waitlist[new_col_info]:
                sus_info.wait_for.remove(new_col_info)
                if not sus_info.released and not sus_info.wait_for:
                    # print(f"release {sus_info.conf = } {sus_info.index = }")
                    sus_info.release()
            del self.waitlist[new_col_info]
    
    def something_here(self) -> bool:
        """ Check if there is anything left in the waitlist. """
        return bool(self.waitlist)
    
    def raise_exception(self, table_name: str) -> NoReturn:
        """ As its name shows. """
        sus_confs: list[_SuspendInfo]
        s: str = ''
        for _, sus_confs in self.waitlist.items():
            for sc in sus_confs:
                s += f"{table_name} {sc.conf["title"]} {sc.index} -> {sc.wait_for}\n"
        raise Exception("DependencyError:\n" + s)
