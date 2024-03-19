from os import PathLike
import re

from tkinter import Frame

from DataMigrator.database import Column, EmptyColumn, FilledColumn, IndexColumn, Table, Database
from DataMigrator.suspended_list import SuspendedList
from DataMigrator import pyjson
from DataMigrator import mapping_functions

def substitute_args(s: str, args: list):
    if re.match(r"_arg[0-9]+", s):
        index: int = int(s[4:])
        return args[index]
    return s

def dereference_column(src_db: Database, tgt_db: Database, table_ref: str, column_ref: str) -> Column:
    src_col: Column
    if re.match(r"_This\..+", table_ref):
        src_col = tgt_db.get_table(
            table_ref[6:]
        ).get_column(
            column_ref
        )
    else:
        src_col = src_db.get_table(
            table_ref
        ).get_column(
            column_ref
        )
    return src_col


def parse_migration_config(fp: PathLike, encoding: str | None = None) -> dict:
    import json
    with open(fp, encoding=encoding, mode='r') as f:
        json_string = f.read()
        valid_chars = r"\u4e00-\u9fa5\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300bA-Za-z#-&\(-@!^_`\|~\\\s"
        json_string = re.sub(r'([{,]\s*)([\u4e00-\u9fa5\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300bA-Za-z!#-&\(-\.0-@^_`|~\\\s]+?):', r'\1"\2":', json_string) # add quotes to keys
        json_string = re.sub(r'([{\[:,][\s\n]*)([\u4e00-\u9fa5\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300bA-Za-z#-&\(-@!^_`|~\\\s]+?)([\s\n]*[,])', r'\1"\2"\3', json_string) # add quotes to values
        json_string = re.sub(r'([:,][\s\n]+)([\u4e00-\u9fa5\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300bA-Za-z#-&\(-@!^_`|~\\\s]+?)([\s\n]*[,\]}])', r'\1"\2"\3', json_string) # add quotes to values with overlapping interval
    return json.loads(json_string)


def process_cconf(src_db: Database, tgt_db: Database, t: Table, col_conf: dict, args: list, pos: int | None = None) -> bool:
    add_column: function
    if pos is None:
        add_column = lambda column_type, **kwargs: t.append_column(
            col_conf["title"],
            col_conf["comment"],
            column_type,
            **kwargs
        )
    else:
        add_column = lambda column_type, **kwargs: t.insert_column(
            pos,
            col_conf["title"],
            col_conf["comment"],
            column_type,
            **kwargs
        )

    if "copy_from" in col_conf:

        src_col: Column = dereference_column(src_db, tgt_db, *col_conf["copy_from"])
        
        if "mapping" in col_conf:
            if isinstance(col_conf["mapping"], dict):
                add_column(
                    Column,
                    data = src_col,
                    mapping = col_conf["mapping"]
                )

            elif isinstance(col_conf["mapping"], str):
                func: function
                try:
                    func = eval("mapping_functions." + col_conf["mapping"])
                except SyntaxError:
                    func = eval(col_conf["mapping"])
                
                add_column(
                    Column,
                    data = src_col,
                    mapping = func
                )
        else:
            add_column(
                Column,
                data = src_col
            )

    elif "index_start" in col_conf:
        add_column(
            IndexColumn,
            start_from = int(substitute_args(col_conf["index_start"], args))
        )
    elif "fill_with" in col_conf:
        add_column(
            FilledColumn,
            filler = substitute_args(col_conf["fill_with"], args)
        )
    elif "dependence" in col_conf:
        try:
            dpd: list[list] = [dereference_column(src_db, tgt_db, *ref).data for ref in col_conf["dependence"]]
        except KeyError:
            return False
        
        l: int = max([len(d) for d in dpd])
        tgt: list = [None] * l
        exec(pyjson.parse(col_conf["script"]))
        add_column(
            Column,
            data = tgt
        )
        
    else:
        add_column(EmptyColumn)
    
    return True


def execute_migration(config: PathLike | dict,
                      src_db: Database,
                      ex_src_db: list[Database],
                      args: list
    ) -> Database:
    """ Migrate data from src_db to the returned database following the migration config from
        the .rjson config file or a dict.

        # Args:
        - config: The path or dict of the .rjson migration config file.
        - src_db: The original database where the source data come from.
        - args: A list of args that would be passed to match the args in the .rjson config
        file.

        # Return:
        - A new database that receive the migrated data.
    """
    tgt_db: Database = Database()
    if not isinstance(config, dict):
        config: dict = parse_migration_config(config, "UTF-8")

    if "process" in config and "pre" in config["process"]:
        exec(pyjson.parse(config["process"]["pre"]))

    sconf: dict
    for sconf in config["sheets"]:
        new_table: Table = tgt_db.add_table(sconf["name"])
        
        sus_list = SuspendedList(lambda conf, index: process_cconf(src_db, tgt_db, new_table, conf, args, index))
        cconf: dict
        for cconf in sconf["columns"]:
            
            sus_list.check(cconf["title"])

            process_succeed: bool = process_cconf(src_db, tgt_db, new_table, cconf, args)

            if not process_succeed:
                # print(f"Suspended - {new_table.name} {cconf["title"]} {suspend_info[1]}")
                sus_list.append(cconf, cconf["dependence"], new_table.suspended_column())
        
        if sus_list.something_here():
            sus_list.raise_exception(new_table.name)
            

    if "process" in config and "post" in config["process"]:
        exec(pyjson.parse(config["process"]["post"]))
    
    return tgt_db
