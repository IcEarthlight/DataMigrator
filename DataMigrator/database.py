from __future__ import annotations

from os import PathLike
from typing import Iterable, Callable, override

import openpyxl
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.worksheet._read_only import ReadOnlyWorksheet
from openpyxl.worksheet._write_only import WriteOnlyWorksheet
from openpyxl.cell.cell import Cell
from openpyxl.cell.read_only import ReadOnlyCell


class Column:
    def __init__(self,
                 title: str,
                 comment: str | None = None,
                 data: list | Column | None = None,
                 mapping: dict | Callable = {"_Other": "_Origin"}
        ):
        self.title: str = title
        self.comment: str = comment if comment else ''
        self.data: list[object]
        
        if data:
            if isinstance(data, list):
                self.data = data.copy()
            elif isinstance(data, Column):
                self.data = data.data.copy()
            
            if isinstance(mapping, dict):
                self.mapping_dict(mapping)
            elif isinstance(mapping, Callable):
                self.mapping_func(mapping)
            
        else:
            self.data = []

    def __str__(self) -> str:
        if self.comment:
            return f"<Column \"{self.title}\" comment = \"{self.comment}\" len(data) = {len(self.data)}>"
        else:
            return f"<Column \"{self.title}\" len(data) = {len(self.data)}>"
    
    def __repr__(self) -> str:
        if self.comment:
            return f"<Column \"{self.title}\" comment = \"{self.comment}\" len(data) = {len(self.data)}>"
        else:
            return f"<Column \"{self.title}\" len(data) = {len(self.data)}>"
        
    def count(self) -> int:
        return len(self.data)
    
    def add_data(self, newData) -> None:
        self.data.append(newData)

    def get_data(self, index: int) -> object | None:
        if index < len(self.data):
            return self.data[index]
        else:
            return None
    
    def swap_row(self, i0: int, i1: int) -> None:
        if i0 == i1:
            return
        if i0 > i1:
            i0, i1 = i1, i0
        if self.count() <= i1:
            self.data.extend([None] * (i1 - self.count() + 1))

        self.data[i0], self.data[i1] = self.data[i1], self.data[i0]
        
    def mapping_func(self, func: Callable) -> None:
        self.data = list(map(lambda s: None if s is None else func(s), self.data))
    
    def mapping_dict(self, mapping: dict) -> None:
        for v in mapping.values():
            if v != "_Origin":
                break
        else:
            return
        
        for i in range(len(self.data)):
            if self.data[i] in mapping:
                m = mapping[self.data[i]]
            else:
                m = mapping["_Other"]

            if m != "_Origin":
                self.data[i] = m


class PlaceHolderColumn(Column):
    def __init__(self):
        Column.__init__(self, '')
    
    @override
    def swap_row(self, i0: int, i1: int) -> None:
        pass

class EmptyColumn(Column):
    def __init__(self, title: str, comment: str | None = None):
        Column.__init__(self, title, comment)
    
    @override
    def count(self) -> int:
        return -1
    
    @override
    def get_data(self, index: int) -> None:
        return None
    
    @override
    def swap_row(self, i0: int, i1: int) -> None:
        pass

class FilledColumn(Column):
    def __init__(self, title: str, comment: str | None = None, filler = None):
        Column.__init__(self, title, comment)
        self.filler = filler
    
    @override
    def count(self) -> int:
        return -1
    
    @override
    def get_data(self, index: int):
        return self.filler
    
    @override
    def swap_row(self, i0: int, i1: int) -> None:
        pass
    
class IndexColumn(Column):
    def __init__(self, title: str, comment: str | None = None, start_from: int = 1):
        Column.__init__(self, title, comment)
        self.start_from: int = start_from
        self.swap_history: dict = {}
    
    @override
    def count(self) -> int:
        return -1

    @override
    def get_data(self, index: int) -> int:
        if index in self.swap_history:
            return self.start_from + self.swap_history[index]
        return self.start_from + index
    
    @override
    def swap_row(self, i0: int, i1: int) -> None:
        self.swap_history[i0] = i1 if i1 not in self.swap_history else self.swap_history[i1]
        self.swap_history[i1] = i0 if i0 not in self.swap_history else self.swap_history[i0]


class Table:
    def __init__(self, name: str, columns: list[Column] | None = None):
        self.name: str = name
        self.columns: list[Column]
        self._column_index: dict[str, int]
        self._max_row_num: int

        if columns:
            self.columns = columns
            self._column_index = {c.title: i for i, c in enumerate(columns)}
            self._max_row_num = max([len(c) for c in columns])
        else:
            self.columns = []
            self._column_index = {}
            self._max_row_num = 0
    
    def __str__(self) -> str:
        return "<Table \"%s\" with %d columns and %d rows>" \
            % (self.name, len(self.columns), self._max_row_num)
    
    def __repr__(self) -> str:
        return "<Table \"%s\" with %d columns and %d rows>" \
            % (self.name, len(self.columns), self._max_row_num)
    
    def _check_new_title(self, new_title: str) -> None:
        """ Check if a title already exists in a table and raise a ValueError for an invalid
            title.
        """
        if new_title in self._column_index:
            raise ValueError("Title already exists.")
    
    def _check_empty_ends(self) -> bool:
        c: Column
        for c in self.columns:
            if len(c.data) < self._max_row_num:
                continue
            if c.data[-1] is not None:
                return False
        return True
    
    def _pop_back(self) -> None:
        c: Column
        self._max_row_num -= 1
        for c in self.columns:
            if c.count() > self._max_row_num:
                del c.data[self._max_row_num:]
    
    def _clear_empty_ends(self) -> None:
        while self._check_empty_ends():
            self._pop_back()

    def append_column(self,
                      title: str,
                      comment: str,
                      column_type: type = Column,
                      **kwargs
        ) -> None:
        """ Append a new column at the end of the table. """
        new_column: Column = column_type(title, comment, **kwargs)
        
        self.columns.append(new_column)
        self._column_index[title] = len(self.columns) - 1
        self._max_row_num = max(new_column.count(), self._max_row_num)

    def extend_columns(self, content: Iterable[tuple[str, str]]) -> None:
        """ Add batch of columns at the end of the table, giving the titles and comments in
            the format of [(title, comment), (title, comment), ...]
        """
        for title, comment in content:
            self.append_column(title, comment)
    
    def suspended_column(self) -> int:
        self.columns.append(PlaceHolderColumn())
        return len(self.columns) - 1
    
    def insert_column(self,
                      index: int,
                      title: str,
                      comment: str,
                      column_type: type = Column,
                      **kwargs
        ) -> None:
        """ Insert a new column in the specified place in a table. Empty Columns would be
            filled in the space.
        """
        if index <= len(self.columns):
            self.columns.extend([PlaceHolderColumn()] * (index - len(self.columns) + 1))
        
        new_column: Column = column_type(title, comment, **kwargs)
        self.columns[index] = new_column
        self._column_index[title] = index
        self._max_row_num = max(new_column.count(), self._max_row_num)
    
    def index(self, column_title: str) -> int:
        """ Returns the index of the column of the given title. Raise a KeyError if no such
            column in the table.
        """
        return self._column_index[column_title]
    
    def get_range(self, reverse=False) -> range:
        if reverse:
            return range(self._max_row_num-1, -1, -1)
        return range(self._max_row_num)
    
    def get_column(self, column_title: str) -> Column:
        """ Returns the column of the given title. Raise a KeyError if no such column in the
            table.
        """
        return self.columns[self._column_index[column_title]]
    
    def swap_row(self, i0: int, i1: int) -> None:
        if i0 == i1:
            return
        if i0 > i1:
            i0, i1 = i1, i0
        if self._max_row_num <= i1:
            raise IndexError(f"row {i1} do not exists")
        
        c: Column
        for c in self.columns:
            c.swap_row(i0, i1)
    
    def move_to_end(self, index: int) -> None:
        if self._max_row_num <= index:
            raise IndexError(f"row {index} do not exists")
        if self._max_row_num - 1 == index:
            return
        
        for i in range(index, self._max_row_num - 1):
            self.swap_row(i, i + 1)
    
    @staticmethod
    def create_from_worksheet(ws: ReadOnlyWorksheet) -> Table:
        t: Table = Table(ws.title)
        
        r: tuple[ReadOnlyCell]
        for i, r in enumerate(ws.rows):

            if not t.columns: # first 
                c: ReadOnlyCell
                for j, c in enumerate(r):
                    t.columns.append(Column(c.value))
                    t._column_index[c.value] = j
                continue
            
            c: ReadOnlyCell
            for j, c in enumerate(r):
                t.columns[j].add_data(c.value)
        else:
            t._max_row_num = i
        
        t._clear_empty_ends()
        return t


class Database:
    def __init__(self):
        self.tables: list[Table] = []
        self._table_index: dict[str, int] = {}

    @staticmethod
    def import_from_xlsx(path: PathLike) -> Database:
        """ Create and return a Database object using the data from a .xlsx file. """
        db: Database = Database()

        wb: Workbook = openpyxl.load_workbook(path, read_only=True)
        ws: ReadOnlyWorksheet
        for i, ws in enumerate(wb.worksheets):
            new_table: Table = Table.create_from_worksheet(ws)
            db.tables.append(new_table)
            db._table_index[new_table.name] = i
        
        wb.close()
        
        return db

    def export_to_xlsx(self, savePath: PathLike, add_note: bool = False) -> None:
        """ Export the Database object to a .xlsx file. """
        wb: Workbook = Workbook(write_only=True)

        table: Table
        for table in self.tables:
            ws: WriteOnlyWorksheet = wb.create_sheet(table.name)
            ws.append([c.title for c in table.columns])
            if add_note:
                ws.append([c.comment for c in table.columns])
            for i in range(table._max_row_num):
                ws.append([c.get_data(i) for c in table.columns])
        # print(savePath)
        wb.save(savePath)
    
    def has_table(self, name: str) -> bool:
        return name in self._table_index
    
    def get_table(self, name: str) -> Table:
        """ Returns the table of the given name. Raise a KeyError if no such table in the
            database.
        """
        return self.tables[self._table_index[name]]

    def add_table(self, name: str) -> Table:
        new_table: Table = Table(name)
        self.tables.append(new_table)
        self._table_index[name] = len(self.tables) - 1
        return new_table
