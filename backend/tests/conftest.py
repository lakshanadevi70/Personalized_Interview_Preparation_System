import os
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.database import Base, get_db
from app.main import app
@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine); Base.metadata.create_all(engine)
    def override():
        db = Session()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db] = override
    with TestClient(app) as result: yield result
    app.dependency_overrides.clear(); Base.metadata.drop_all(engine); engine.dispose()
