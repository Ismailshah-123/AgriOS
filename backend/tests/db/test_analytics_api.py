"""GET /analytics: grouped sums and counts from the caller's own records only."""

import pytest
from fastapi.testclient import TestClient

from tests.images import make_image
from tests.support import API, create_cycle, create_farm, create_field, crop_id, register

pytestmark = pytest.mark.db


def test_empty_account_has_zeroes_not_estimates(db_client: TestClient) -> None:
    h = register(db_client, "an-empty@example.com")
    a = db_client.get(f"{API}/analytics", headers=h).json()
    assert a["area_by_crop"] == [] and a["pending_expert_reviews"] == 0
    assert len(a["cases"]["by_month"]) == 6 and all(m["cases"] == 0 for m in a["cases"]["by_month"])
    e = a["economics"]
    assert (e["currency"], e["total_cost_pkr"], e["profit_pkr"], e["cycles"]) == (
        "PKR",
        "0.00",
        "0.00",
        [],
    )


def test_aggregates_area_cases_and_money_and_ignores_other_users(db_client: TestClient) -> None:
    h = register(db_client, "an@example.com")
    farm = create_farm(db_client, h)
    f1 = create_field(db_client, h, farm["id"], value="2", unit="ha")
    f2 = create_field(db_client, h, farm["id"], name="East", value="1", unit="ha")
    tomato = create_cycle(db_client, h, f1["id"], status="active", sowing_date="2026-10-01")
    db_client.post(
        f"{API}/crop-cycles",
        headers=h,
        json={
            "field_id": f2["id"],
            "crop_id": crop_id(db_client, h, "wheat"),
            "status": "active",
            "sowing_date": "2026-11-01",
        },
    ).raise_for_status()
    for cat, amt in [("seed", "1000.00"), ("labour", "500.50")]:
        db_client.post(
            f"{API}/expenses",
            headers=h,
            json={
                "crop_cycle_id": tomato["id"],
                "category": cat,
                "amount_pkr": amt,
                "incurred_on": "2026-10-05",
            },
        ).raise_for_status()
    db_client.post(
        f"{API}/harvest-sales",
        headers=h,
        json={
            "crop_cycle_id": tomato["id"],
            "recorded_on": "2026-11-10",
            "quantity_kg": "100",
            "price_pkr_per_kg": "30",
        },
    ).raise_for_status()
    case = db_client.post(
        f"{API}/cases",
        headers=h,
        data={"crop_cycle_id": tomato["id"]},
        files=[("images", ("a.jpg", make_image(), "image/jpeg"))],
    ).json()
    db_client.post(f"{API}/cases/{case['id']}/expert-review", headers=h)

    other = register(db_client, "an-other@example.com")  # sees none of it
    assert db_client.get(f"{API}/analytics", headers=other).json()["economics"]["cycles"] == []

    a = db_client.get(f"{API}/analytics", headers=h).json()
    assert {(r["crop"], r["cycles"], r["area_ha"]) for r in a["area_by_crop"]} == {
        ("Tomato", 1, 2.0),
        ("Wheat", 1, 1.0),
    }
    assert a["cases"]["by_status"]["expert_review"] == 1 and a["pending_expert_reviews"] == 1
    assert a["cases"]["by_month"][-1]["cases"] == 1  # created this month
    e = a["economics"]
    assert (e["total_cost_pkr"], e["total_revenue_pkr"], e["profit_pkr"]) == (
        "1500.50",
        "3000.00",
        "1499.50",
    )
    assert e["cost_by_category_pkr"] == {"seed": "1000.00", "labour": "500.50"}
    assert [(c["crop"], c["profit_pkr"]) for c in e["cycles"]] == [("Tomato", "1499.50")]
