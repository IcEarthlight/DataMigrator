"""
DataMigrator provides a series of classes and functions that helps you to manage, operate,
and transfer data from/to excel files, which enables you to migrate data from one (or
maybe more) file(s) to another with ease.

.rjson config file is the core feature of DataMigrator. It is a simple, easy-to-handle
while powerful tool, containing all the instructions of dealing with the input data, the
column mapping, pre- and post-processing, and anything you want to apply to your data. Its
format follows a variation of relaxed json. In .rjson for DataMigrator, you don't have to
add quotes to the keys and values that do not contains any following symbols '",:[]{}, and
spaces are allowed to the keys and values without quotes too. For more details about .rjson
config file, see About_rjson.md

Once you have your config file, you can easily apply it to the data either through GUI or
by using function execute_migration() in DataMigrator.migration_toolkit. Most function and
core logics are well-wrapped so that you don't need to care much about how it works.

Example: (GUI)
``` python
from DataMigrator import migrator_gui
migrator_gui.MigratorUI()
```

Example: (Script)
``` python
from os import PathLike
from DataMigrator.database import Database
from DataMigrator import migration_toolkit as mt

read_path: PathLike = "./src_data.xlsx"
save_path: PathLike = "./output.xlsx"
config_path: PathLike = "./DemoConfig.rjson"

src_db: Database = Database.import_from_xlsx(read_path)
write_db = mt.execute_migration(config_path, src_db)
write_db.export_to_xlsx(save_path)
```
"""

__version__ = "1.0.3"
