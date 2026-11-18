import pytest

from controls_monitor import models  # noqa: F401
from controls_monitor.db import (
    TEST_DATABASE_URL,
    Base,
    make_engine,
    make_session_factory,
)
from controls_monitor.init_db import truncate_all


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
        truncate_all(engine)