import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "CONTROLS_DATABASE_URL",
    "postgresql+psycopg2://controls:controls@localhost:5435/controls_db",
)
TEST_DATABASE_URL = os.getenv(
    "CONTROLS_TEST_DATABASE_URL",
    "postgresql+psycopg2://controls:controls@localhost:5435/controls_test_db",
)


class Base(DeclarativeBase):
    pass


def make_engine(url=None):
    return create_engine(url or DATABASE_URL, pool_pre_ping=True)


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)