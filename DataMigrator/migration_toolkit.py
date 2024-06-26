from os import PathLike
import re

import DataMigrator
from DataMigrator.database import Column, EmptyColumn, FilledColumn, IndexColumn, Table, Database
from DataMigrator.suspended_list import SuspendedList
from DataMigrator import pjshon
from DataMigrator import mapping_functions


def parse_migration_config(fp: PathLike, encoding: str | None = None) -> dict:
    """ Convert the .rjson format to the standard format using a set of regular expressions
        so that it can be parsed by the buildin json parser.

        # Raises
        - json.decoder.JSONDecodeError if there is any invalid syntax.
    """
    import json
    with open(fp, encoding=encoding, mode='r') as f:
        json_string = f.read()

        entry_start: int = 0
        entry_end: int = 0
        in_entry: bool = False
        in_quote: bool = False
        add_quote_list: list[int] = []

        for i, c in enumerate(json_string):
            if c == '"':
                in_quote = not in_quote
            elif not in_quote:
                if re.match(r"[\{\}\[\],:]", c):
                    if in_entry:
                        add_quote_list.append(entry_start)
                        add_quote_list.append(entry_end)
                        in_entry = False
                elif not re.match(r"\s", c):
                    if not in_entry:
                        entry_start = i
                        in_entry = True
                    entry_end = i + 1

        add_quote_list = [0] + add_quote_list + [len(json_string)]
        json_string = '"'.join([json_string[add_quote_list[i]:add_quote_list[i+1]] for i in range(len(add_quote_list) - 1)])
    
    conf: dict = json.loads(json_string)
    if "version" in conf and conf["version"] > DataMigrator.__version__:
        raise Exception(f"DataMigrator {conf["version"]} is required to parse the config, " \
                        f"the current version is {DataMigrator.__version__}, please keep " \
                        f"the package up-to-date.")
        
    return conf


def substitute_args(s: str, args: list):
    """ Substitute argment values for the keyword (such as "_arg03") in config. """
    if re.match(r"_arg[0-9]+", s):
        index: int = int(s[4:])
        return args[index]
    return s


def dereference_column(src_db: Database,
                       ex_src_db: list[Database],
                       sub_db: Database,
                       tgt_db: Database,
                       table_ref: str,
                       column_ref: str
    ) -> Column:
    """ Parse the fields in the config and return the column object that is referred. """
    src_col: Column
    if re.match(r"_This\..+", table_ref):
        src_col = tgt_db.get_table(
            table_ref[6:]
        ).get_column(
            column_ref
        )
    elif match := re.match(r"(_Add)([0-9]+)\.(.+)", table_ref):
        add_index: int = int(match.group(2))
        table_name: str = match.group(3)

        src_col = ex_src_db[add_index].get_table(
            table_name
        ).get_column(
            column_ref
        )
    elif match := re.match(r"(_Sub)([0-9]+)", table_ref):
        sub_index: int = int(match.group(2))
        src_col = sub_db.tables[sub_index].get_column(column_ref, True)
    else:
        src_col = src_db.get_table(
            table_ref
        ).get_column(
            column_ref
        )
    return src_col


def process_cconf(src_db: Database,
                  ex_src_db: list[Database],
                  sub_db: Database,
                  tgt_db: Database,
                  t: Table,
                  col_conf: dict,
                  args: list,
                  pos: int | None = None
    ) -> bool:
    """ Migrate a column from source Database and extra Databases to the target Database
        following the config in col_conf.

        # Args
        - src_db: source Database
        - ex_src_db: a list of extra source Databases
        - tgt_db: target Database
        - t: the target table that would accept write-in data
        - col_conf: a dict contains config of column migration
        - args: A list of args that would be passed to match the args in the .rjson config
        file.
        - pos: specify it if the new column is inserted into the table in given index position
        (by default the new column would be appended at the end of the table)

        # Return
        - A bool value. True if the column is successfully processed and appended (or
        inserted); False if this process requires data from columns that haven't been read
        yet. In this case a placeholder column would be appended instead, and this process
        would be suspended and add into the suspended waitlist until the required column is
        available.
    """
    add_column: function
    if pos:
        add_column = lambda column_type, **kwargs: t.insert_column(
            pos,
            col_conf["title"],
            col_conf.get("comment"),
            column_type,
            **kwargs
        )
    else:
        add_column = lambda column_type, **kwargs: t.append_column(
            col_conf["title"],
            col_conf.get("comment"),
            column_type,
            **kwargs
        )

    if "copy_from" in col_conf:
        try:
            src_col: Column = dereference_column(src_db, ex_src_db, sub_db,
                                                 tgt_db, *col_conf["copy_from"])
        except KeyError as e:
            return False
        
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
            dpd: list[list] = [dereference_column(src_db, ex_src_db, sub_db, tgt_db, *ref).data
                               for ref in col_conf["dependence"]]
        except KeyError as e:
            print(type(e).__name__, e)
            return False
        
        l: int = len(dpd[0])
        tgt: list = [None] * l
        context: dict[str: ...] = {'l': l, "tgt": tgt, "dpd": dpd, "args": args}

        exec(pjshon.parse(col_conf["script"]), context)
        add_column(
            Column,
            data = context["tgt"]
        )
        
    else:
        add_column(EmptyColumn)
    
    return True


def get_sub_db(config: PathLike | dict, src_db: Database) -> Database:
    """ Get the sub tables packed in a database from the source database. """
    sub_db = Database()
    if not isinstance(config, dict):
        config: dict = parse_migration_config(config, "UTF-8")
    
    if "process" in config and "subsheets" in config["process"]:
        subsheet_conf: list[list] = config["process"]["subsheets"]
    else:
        return sub_db
    
    for sconf in subsheet_conf:
        src_table: Table = src_db.get_table(sconf[0])
        sub_table: Table = src_table.get_subtable(int(sconf[1][0][0]), int(sconf[1][1][0]),
                                                  int(sconf[1][0][1]), int(sconf[1][1][1]))
        sub_db.tables.append(sub_table)

    return sub_db

def execute_migration(config: PathLike | dict,
                      src_db: Database,
                      ex_src_db: list[Database] = [],
                      args: list = []
    ) -> Database:
    """ Migrate data from src_db to the returned database following the migration config from
        the .rjson config file or a dict.

        # Args
        - config: The path or dict of the .rjson migration config file.
        - src_db: The original database where the source data come from.
        - ex_src_db: A list contains additional input databases if required, can be empty.
        - args: A list of args that would be passed to match the args in the .rjson config
        file.

        # Return
        - A new database that receive the migrated data.
    """
    tgt_db: Database = Database()
    if not isinstance(config, dict):
        config: dict = parse_migration_config(config, "UTF-8")
    sub_db: Database = get_sub_db(config, src_db)

    context: dict[str: ...] = {"config": config, "src_db": src_db, "sub_db": sub_db,
                               "ex_src_db": ex_src_db, "tgt_db": tgt_db, "args": args,
                               "Database": Database, "Table": Table, "Column": Column,
                               "DataMigrator": DataMigrator, "EmptyColumn": EmptyColumn,
                               "FilledColumn": FilledColumn, "IndexColumn": IndexColumn,
                               "SuspendedList": SuspendedList, "pjshon": pjshon,
                               "mapping_functions": mapping_functions, "config": config,
                               "substitute_args": substitute_args,
                               "dereference_column": dereference_column,
                               "parse_migration_config": parse_migration_config,
                               "process_cconf": process_cconf,
                               "get_sub_db": get_sub_db}
    if "process" in config and "pre" in config["process"]:
        exec(pjshon.parse(config["process"]["pre"]), context)
    src_db = context["src_db"]
    sub_db = context["sub_db"]
    ex_src_db = context["ex_src_db"]
    tgt_db = context["tgt_db"]
    config = context["config"]
    args = context["args"]

    sconf: dict
    for sconf in config["sheets"]:
        new_table: Table = tgt_db.add_table(sconf["name"])
        
        sus_list = SuspendedList(lambda conf, ind: process_cconf(src_db, ex_src_db, sub_db,
                                                                 tgt_db, new_table, conf,
                                                                 args, ind))
        cconf: dict
        for cconf in sconf["columns"]:

            process_succeed: bool = process_cconf(src_db, ex_src_db, sub_db,
                                                  tgt_db, new_table, cconf, args)

            if not process_succeed:
                if "copy_from" in cconf:
                    sus_list.append(cconf,
                                    sconf["name"],
                                    [cconf["copy_from"]],
                                    new_table.suspended_column())
                else:
                    sus_list.append(cconf,
                                    sconf["name"],
                                    cconf["dependence"],
                                    new_table.suspended_column())
                # print(f"Suspended - {new_table.name} {cconf["title"]}")
            else:
                sus_list.check((sconf["name"], cconf["title"]))
        
    if "sus_list" in locals().keys() and sus_list.something_here():
        sus_list.raise_exception(new_table.name)
            
    context: dict[str: ...] = {"config": config, "src_db": src_db, "sub_db": sub_db,
                               "ex_src_db": ex_src_db, "tgt_db": tgt_db, "args": args,
                               "Database": Database, "Table": Table, "Column": Column,
                               "SuspendedList": SuspendedList, "pjshon": pjshon,
                               "DataMigrator": DataMigrator, "EmptyColumn": EmptyColumn,
                               "FilledColumn": FilledColumn, "IndexColumn": IndexColumn,
                               "mapping_functions": mapping_functions, "config": config,
                               "substitute_args": substitute_args,
                               "dereference_column": dereference_column,
                               "parse_migration_config": parse_migration_config,
                               "process_cconf": process_cconf,
                               "get_sub_db": get_sub_db}
    if "process" in config and "post" in config["process"]:
        exec(pjshon.parse(config["process"]["post"]), context)
    src_db = context["src_db"]
    sub_db = context["sub_db"]
    ex_src_db = context["ex_src_db"]
    tgt_db = context["tgt_db"]
    
    return tgt_db
