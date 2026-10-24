"""Shared fixtures: a small controlled CSV and a temporary database per test.

Expected results for FIXTURE_CSV (hand-calculated):

  eligible (Completed, price known):
    T1  Jan  A North  2 x 100 - 0   = 200
    T2  Jan  B South  1 x 500 - 50  = 450
    T3  Feb  A South  3 x 100 - 0   = 300
    T5  Feb  C North  4 x  50 - 0   = 200
    T7  Mar  A East   0 x 100 - 0   =   0   (zero quantity: counted, flagged)
  excluded but stored: T4 (Returned), T6 (missing unit price)
  rejected: duplicate T2, T8 (invalid date), T9 (negative qty), T10 (bad price)

  total = 1150 over 5 transactions; Jan 650, Feb 500, Mar 0
  products: A 500, B 450, C 200      regions: South 750, North 400, East 0
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

FIXTURE_CSV = """Transaction_Id,Order_date,Product,Category,Region,Sales_channel,Quantity,Unit_price,Discount_amount,Status
T1,05-01-2026,A,Cat1,North,Online,2,100,0,Completed
T2,10-01-2026,B,Cat2,South,Retail,1,500,50,Completed
T3,15-02-2026,A,Cat1,South,Online,3,100,0,Completed
T4,20-02-2026,B,Cat2,North,Retail,1,500,0,Returned
T5,25-02-2026,C,Cat1,North,Online,4,50,0,Completed
T2,11-01-2026,B,Cat2,South,Retail,9,500,0,Completed
T6,01-03-2026,C,Cat1,North,Online,5,,0,Completed
T7,02-03-2026,A,Cat1,East,Online,0,100,0,Completed
T8,31-02-2026,A,Cat1,East,Online,1,100,0,Completed
T9,03-03-2026,A,Cat1,East,Online,-1,100,0,Completed
T10,04-03-2026,A,Cat1,East,Online,1,abc,0,Completed
"""

BACKEND_DIR = Path(__file__).resolve().parent.parent
REAL_CSV = BACKEND_DIR / "data" / "sales_data.csv"


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.csv"
    path.write_text(FIXTURE_CSV, encoding="utf-8")
    return path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def settings(csv_path: Path, db_path: Path) -> Settings:
    return Settings(db_path=db_path, csv_path=csv_path)


@pytest.fixture
def loaded_db(csv_path: Path, db_path: Path) -> Path:
    from app.data_loader import import_csv

    import_csv(csv_path, db_path)
    return db_path


@pytest.fixture
def client(settings: Settings):
    app = create_app(settings, llm_client=None)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
