import sys
from sqlalchemy import inspect
from controls_monitor import models  # noqa: F401 
from controls_monitor.db import Base, make_engine


def create_tables(engine):
    Base.metadata.create_all(engine)


def drop_tables(engine):
    Base.metadata.drop_all(engine)


def main():
    engine = make_engine()
    if "--reset" in sys.argv:
        drop_tables(engine)
        print("dropped all tables")
    create_tables(engine)
    print("tables:", ", ".join(sorted(inspect(engine).get_table_names())))


if __name__ == "__main__":
    main()