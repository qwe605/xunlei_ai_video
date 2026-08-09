from sqlalchemy import Engine, inspect, text


def migrate_existing_database(engine: Engine) -> None:
    """补齐 create_all 无法修改的旧 SQLite 表结构。

    原生 SQL 只允许集中在迁移模块；Controller 和 Service 始终使用 ORM。
    """

    inspector = inspect(engine)
    if "analysis_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("analysis_jobs")}
    if "owner_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE analysis_jobs "
                    "ADD COLUMN owner_id VARCHAR(120) NOT NULL DEFAULT 'demo-local'"
                )
            )
