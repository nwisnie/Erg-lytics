from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import rowlytics_app.services.dynamodb as dynamodb


def make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "boom"}}, "TestOp")


def test_now_iso_returns_timezone_aware_isoformat() -> None:
    ts = dynamodb.now_iso()
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
    assert ts.endswith("+00:00")


def test_get_resource_requires_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamodb, "boto3", None)
    with pytest.raises(RuntimeError):
        dynamodb._get_resource()


def test_get_resource_uses_boto3_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    resource = MagicMock()
    boto = MagicMock()
    boto.resource.return_value = resource
    monkeypatch.setattr(dynamodb, "boto3", boto)
    assert dynamodb._get_resource() is resource
    boto.resource.assert_called_once_with("dynamodb")


def test_get_users_table_returns_table(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    resource = MagicMock()
    resource.Table.return_value = table
    monkeypatch.setattr(dynamodb, "_get_resource", lambda: resource)
    assert dynamodb.get_users_table() is table
    resource.Table.assert_called_once_with(dynamodb.USERS_TABLE_NAME)


def test_get_team_members_table_returns_table(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    resource = MagicMock()
    resource.Table.return_value = table
    monkeypatch.setattr(dynamodb, "_get_resource", lambda: resource)
    assert dynamodb.get_team_members_table() is table
    resource.Table.assert_called_once_with(dynamodb.TEAM_MEMBERS_TABLE_NAME)


def test_get_teams_table_returns_table(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    resource = MagicMock()
    resource.Table.return_value = table
    monkeypatch.setattr(dynamodb, "_get_resource", lambda: resource)
    assert dynamodb.get_teams_table() is table
    resource.Table.assert_called_once_with(dynamodb.TEAMS_TABLE_NAME)


def test_get_recordings_table_raises_when_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamodb, "RECORDINGS_TABLE_NAME", "")
    with pytest.raises(RuntimeError):
        dynamodb.get_recordings_table()


def test_get_ddb_tables_returns_user_and_member_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    users_table = MagicMock(name="users_table")
    members_table = MagicMock(name="members_table")
    monkeypatch.setattr(dynamodb, "get_users_table", lambda: users_table)
    monkeypatch.setattr(dynamodb, "get_team_members_table", lambda: members_table)
    result = dynamodb.get_ddb_tables()
    assert result == (users_table, members_table)


def test_sync_user_profile_returns_name_when_no_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamodb, "get_users_table", lambda: pytest.fail("should not call"))
    name = dynamodb.sync_user_profile(None, "user@example.com", "Row Rower")
    assert name == "Row Rower"


def test_sync_user_profile_updates_with_email_and_derived_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = MagicMock()
    table.update_item.return_value = {"Attributes": {"name": "Updated"}}
    monkeypatch.setattr(dynamodb, "get_users_table", lambda: table)

    name = dynamodb.sync_user_profile("u1", "rower@example.com", None)

    assert name == "Updated"
    update_expr = (
        "SET #name = if_not_exists(#name, :name), "
        "createdAt = if_not_exists(createdAt, :createdAt), "
        "email = if_not_exists(email, :email)"
    )
    args, kwargs = table.update_item.call_args
    assert kwargs["Key"] == {"userId": "u1"}
    assert kwargs["UpdateExpression"] == update_expr
    assert kwargs["ExpressionAttributeValues"][":name"] == "rower"
    assert kwargs["ExpressionAttributeValues"][":email"] == "rower@example.com"


def test_sync_user_profile_returns_original_name_on_update_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = MagicMock()
    table.update_item.side_effect = Exception("boom")
    monkeypatch.setattr(dynamodb, "get_users_table", lambda: table)

    result = dynamodb.sync_user_profile("u1", "u@example.com", "Name")
    assert result == "Name"


def test_batch_get_users_returns_empty_dict_when_no_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    table.meta = SimpleNamespace(client=MagicMock())
    assert dynamodb.batch_get_users(table, []) == {}
    table.meta.client.batch_get_item.assert_not_called()


def test_batch_get_users_handles_chunking(monkeypatch: pytest.MonkeyPatch) -> None:
    user_ids = [f"id{i}" for i in range(120)]
    client = MagicMock()
    client.batch_get_item.side_effect = [
        {"Responses": {"Users": [{"userId": f"id{i}"} for i in range(100)]}},
        {"Responses": {"Users": [{"userId": f"id{i}"} for i in range(100, 120)]}},
    ]
    table = MagicMock()
    table.name = "Users"
    table.meta = SimpleNamespace(client=client)

    result = dynamodb.batch_get_users(table, user_ids)

    assert len(result) == 120
    assert result["id0"]["userId"] == "id0"
    assert result["id119"]["userId"] == "id119"
    assert client.batch_get_item.call_count == 2


def test_batch_get_users_propagates_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.batch_get_item.side_effect = Exception("fail")
    table = MagicMock()
    table.name = "Users"
    table.meta = SimpleNamespace(client=client)

    with pytest.raises(Exception):
        dynamodb.batch_get_users(table, ["u1"])


def test_fetch_team_members_merges_users_and_normalizes_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team_members_table = MagicMock()
    team_members_table.query.return_value = {
        "Items": [
            {"userId": "u1", "memberRole": "Coach", "joinedAt": "2024-01-01"},
            {"userId": "u2", "memberRole": "admin", "joinedAt": "2024-01-02"},
            {"userId": "u3", "memberRole": None, "joinedAt": "2024-01-03"},
        ]
    }
    users_by_id = {
        "u1": {"name": "Coach User", "email": "c@example.com"},
        "u2": {"name": "Admin User", "email": "a@example.com"},
    }
    monkeypatch.setattr(dynamodb, "batch_get_users", lambda _table, ids: users_by_id)

    members = dynamodb.fetch_team_members(
        users_table=MagicMock(),
        team_members_table=team_members_table,
        team_id="team1",
        allowed_roles={"coach", "rower"},
    )

    assert members[0]["memberRole"] == "coach"
    assert members[1]["memberRole"] == "rower"
    assert members[2]["memberRole"] == "rower"
    assert members[0]["email"] == "c@example.com"


def test_get_team_membership_returns_first_item(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    table.query.return_value = {"Items": [{"teamId": "t1"}]}
    assert dynamodb.get_team_membership(table, "u1") == {"teamId": "t1"}


def test_get_team_membership_returns_none_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    table = MagicMock()
    table.query.return_value = {"Items": []}
    assert dynamodb.get_team_membership(table, "u1") is None


def test_get_team_membership_fallbacks_to_scan_on_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = MagicMock()
    table.query.side_effect = make_client_error("ValidationException")
    table.scan.return_value = {"Items": [{"userId": "u1", "teamId": "t1"}]}

    result = dynamodb.get_team_membership(table, "u1")
    assert result == {"userId": "u1", "teamId": "t1"}
    table.scan.assert_called_once()


def test_get_team_membership_reraises_unexpected_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = MagicMock()
    table.query.side_effect = make_client_error("AccessDenied")
    with pytest.raises(ClientError):
        dynamodb.get_team_membership(table, "u1")


def test_get_team_returns_item() -> None:
    table = MagicMock()
    table.get_item.return_value = {"Item": {"teamId": "t1"}}
    assert dynamodb.get_team(table, "t1") == {"teamId": "t1"}


def test_get_team_returns_none_when_not_found() -> None:
    table = MagicMock()
    table.get_item.return_value = {}
    assert dynamodb.get_team(table, "t1") is None


def test_get_team_propagates_errors() -> None:
    table = MagicMock()
    table.get_item.side_effect = Exception("boom")
    with pytest.raises(Exception):
        dynamodb.get_team(table, "t1")


def test_query_all_handles_multiple_pages() -> None:
    table = MagicMock()
    table.query.side_effect = [
        {"Items": [{"id": 1}], "LastEvaluatedKey": "token"},
        {"Items": [{"id": 2}]},
    ]

    result = dynamodb.query_all(table, KeyConditionExpression=MagicMock())
    assert result == [{"id": 1}, {"id": 2}]
    assert table.query.call_count == 2


def test_scan_all_handles_multiple_pages() -> None:
    table = MagicMock()
    table.scan.side_effect = [
        {"Items": [{"id": 1}], "LastEvaluatedKey": "token"},
        {"Items": [{"id": 2}]},
    ]

    result = dynamodb.scan_all(table, FilterExpression=MagicMock())
    assert result == [{"id": 1}, {"id": 2}]
    assert table.scan.call_count == 2


def test_list_team_memberships_uses_query_all(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def fake_query_all(table, **kwargs):
        called["kwargs"] = kwargs
        return [1, 2]

    monkeypatch.setattr(dynamodb, "query_all", fake_query_all)
    table = MagicMock()
    result = dynamodb.list_team_memberships(table, "u1")

    assert result == [1, 2]
    assert "KeyConditionExpression" in called["kwargs"]
    assert called["kwargs"]["IndexName"] == dynamodb.TEAM_MEMBERS_USER_INDEX


def test_list_team_memberships_falls_back_to_scan_on_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_query_all(*_, **__):
        raise make_client_error("ValidationException")

    monkeypatch.setattr(dynamodb, "query_all", raise_query_all)
    monkeypatch.setattr(dynamodb, "scan_all", lambda *_, **__: ["fallback"])

    table = MagicMock()
    result = dynamodb.list_team_memberships(table, "u1")
    assert result == ["fallback"]


def test_list_team_members_by_team_delegates_to_query_all(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_query_all(table, **kwargs):
        captured.update(kwargs)
        return ["member"]

    monkeypatch.setattr(dynamodb, "query_all", fake_query_all)
    table = MagicMock()
    result = dynamodb.list_team_members_by_team(table, "team1")

    assert result == ["member"]
    assert "KeyConditionExpression" in captured


def test_list_owned_teams_returns_empty_when_attr_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamodb, "Attr", None)
    assert dynamodb.list_owned_teams(MagicMock(), "u1") == []


def test_list_owned_teams_calls_scan_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamodb, "scan_all", lambda *_, **__: ["owned"])
    result = dynamodb.list_owned_teams(MagicMock(), "coach123")
    assert result == ["owned"]


def test_list_recordings_delegates_to_query_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamodb, "query_all", lambda *_, **__: ["recording"])
    result = dynamodb.list_recordings(MagicMock(), "u1")
    assert result == ["recording"]


def test_team_name_exists_returns_false_for_empty_name() -> None:
    assert dynamodb.team_name_exists(MagicMock(), "") is False


def test_team_name_exists_raises_when_attr_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dynamodb, "Attr", None)
    with pytest.raises(RuntimeError):
        dynamodb.team_name_exists(MagicMock(), "Team")


def test_team_name_exists_true_when_query_returns_item() -> None:
    teams_table = MagicMock()
    teams_table.query.return_value = {"Items": [{"teamName": "T"}]}
    assert dynamodb.team_name_exists(teams_table, "T") is True


def test_team_name_exists_uses_scan_when_query_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    teams_table = MagicMock()
    teams_table.query.return_value = {"Items": []}
    teams_table.scan.return_value = {"Items": [{"teamName": "T"}]}

    assert dynamodb.team_name_exists(teams_table, "T") is True
    teams_table.scan.assert_called_once()


def test_team_name_exists_fallback_on_allowed_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    teams_table = MagicMock()
    teams_table.query.side_effect = make_client_error("ValidationException")
    teams_table.scan.return_value = {"Items": [{"teamName": "T"}]}

    assert dynamodb.team_name_exists(teams_table, "T") is True
    teams_table.scan.assert_called_once()


def test_team_name_exists_reraises_unexpected_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    teams_table = MagicMock()
    teams_table.query.side_effect = make_client_error("AccessDenied")

    with pytest.raises(ClientError):
        dynamodb.team_name_exists(teams_table, "T")
