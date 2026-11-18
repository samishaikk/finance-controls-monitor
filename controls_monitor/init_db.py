import sys

from sqlalchemy import inspect, text
from controls_monitor import models  # noqa: F401  (registers the tables)
from controls_monitor.db import Base, make_engine


def create_tables(engine):
    Base.metadata.create_all(engine)


def drop_tables(engine):
    Base.metadata.drop_all(engine)


def truncate_all(engine):
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def main():
    engine = make_engine()
    if "--reset" in sys.argv:
        drop_tables(engine)
        print("dropped all tables")
    create_tables(engine)
    print("tables:", ", ".join(sorted(inspect(engine).get_table_names())))


if __name__ == "__main__":
    main()