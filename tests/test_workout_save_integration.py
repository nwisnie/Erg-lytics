from decimal import Decimal

import boto3
import pytest

from rowlytics_app import create_app


class FakeWorkoutsTable:
    def __init__(self):
        self.items = []

    def put_item(self, Item):
        self.items.append(Item)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


class FakeDynamoResource:
    def __init__(self):
        self.workouts_table = FakeWorkoutsTable()

    def Table(self, table_name):
        return self.workouts_table


@pytest.fixture()
def fake_dynamo(monkeypatch):
    fake_resource = FakeDynamoResource()

    monkeypatch.setenv("ROWLYTICS_WORKOUTS_TABLE", "RowlyticsWorkouts")

    monkeypatch.setattr(
        boto3,
        "resource",
        lambda *args, **kwargs: fake_resource,
    )

    return fake_resource


@pytest.fixture()
def app(fake_dynamo):
    flask_app = create_app()
    flask_app.config.update(TESTING=True, AUTH_REQUIRED=False)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_save_workout_route_persists_analysis_fields(client, fake_dynamo):
    with client.session_transaction() as session:
        session["user_id"] = "test-user-123"

    response = client.post(
        "/api/workouts",
        json={
            "workoutId": "workout-123",
            "durationSec": 120,
            "summary": "Good workout",
            "workoutScore": 67.5,
            "alignmentDetails": "clips observed: 3",
            "strokeCount": 12,
            "cadenceSpm": 24.5,
            "rangeOfMotion": 0.31,
            "armsStraightScore": 72.0,
            "backStraightScore": 88.0,
            "dominantSide": "left",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["status"] == "ok"

    saved_item = fake_dynamo.workouts_table.items[0]

    assert saved_item["userId"] == "test-user-123"
    assert saved_item["workoutId"] == "workout-123"
    assert saved_item["durationSec"] == 120
    assert saved_item["summary"] == "Good workout"
    assert saved_item["alignmentDetails"] == "clips observed: 3"
    assert saved_item["strokeCount"] == 12
    assert saved_item["workoutScore"] == Decimal("67.5")
    assert saved_item["cadenceSpm"] == Decimal("24.5")
    assert saved_item["rangeOfMotion"] == Decimal("0.31")
    assert saved_item["armsStraightScore"] == Decimal("72.0")
    assert saved_item["backStraightScore"] == Decimal("88.0")
    assert saved_item["dominantSide"] == "left"