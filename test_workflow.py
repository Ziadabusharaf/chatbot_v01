from datetime import datetime

from app import app


def test_job_workflow():
    client = app.test_client()

    payload = {
        "job_number": f"ATL-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        "builder": "Sunrise Homes",
        "community": "West Grove",
        "address": "101 Main St",
        "plan_number": "Plan-A1",
        "material": "Quartz Calacatta",
        "thickness_mm": 30,
        "created_by_email": "ac@stoneops.local",
        "areas": [
            {
                "area_name": "Kitchen",
                "sink_model": "K-9920",
                "appliance_model": "DW-300",
                "edge_profile": "Eased",
                "backsplash": "4in",
                "overhang_inches": 1.5,
                "required_photos_count": 2,
                "uploaded_photos_count": 2,
            }
        ],
    }

    create_res = client.post("/api/jobs", json=payload)
    assert create_res.status_code == 201
    job_id = create_res.get_json()["job_id"]

    schedule_res = client.post(
        f"/api/jobs/{job_id}/schedule",
        json={
            "templater_email": "templater@stoneops.local",
            "templater_role": "templater_in_house",
            "scheduled_start": "2026-04-22T09:00:00",
            "scheduled_end": "2026-04-22T11:00:00",
            "readiness_confirmed": True,
        },
    )
    assert schedule_res.status_code == 200

    submit_res = client.post(
        f"/api/jobs/{job_id}/field-submission",
        json={
            "templater_email": "templater@stoneops.local",
            "has_signature": True,
            "is_offline_synced": True,
        },
    )
    assert submit_res.status_code == 200

    review_res = client.post(f"/api/jobs/{job_id}/ai-review")
    assert review_res.status_code == 200
    assert review_res.get_json()["ai_review"]["recommendation"] == "ready_for_review"
