from os import PathLike

from DataMigrator.database import Database
from DataMigrator import migration_toolkit as mt

read_path: PathLike = "./src_data.xlsx"
save_path: PathLike = "./output.xlsx"

src_db: Database = Database.import_from_xlsx(read_path)
write_db = mt.execute_migration("./MigrationConfig3.rjson", src_db, [], ["MSA", 'D'])

write_db.export_to_xlsx(save_path, False)
