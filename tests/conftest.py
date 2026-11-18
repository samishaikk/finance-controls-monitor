import pytest
from sqlalchemy import text
from controls_monitor import models  # noqa: F401
from controls_monitor.db import (
    TEST_DATABASE_URL,
    Base,
    make_engine,
    make_session_factory,
)


@pytest.fixture(scope="session")
def engine():
    engine = make_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(engine):
    session = make_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))