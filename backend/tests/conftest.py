import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://test:test@localhost:5432/levelmind_test"
)
os.environ["SUPABASE_URL"] = "https://test.supabase.co"

from app.auth import AuthenticatedUser, get_current_user  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        yield session

    engine.dispose()


@pytest.fixture(autouse=True)
def override_database_dependency(db_session: Session) -> Iterator[None]:
    def get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def authenticated_user_id() -> Iterator[UUID]:
    user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=user_id
    )
    yield user_id
    app.dependency_overrides.pop(get_current_user, None)
