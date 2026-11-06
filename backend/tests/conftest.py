import os
import sys
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

