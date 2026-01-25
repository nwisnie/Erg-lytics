"""DynamoDB helpers for Rowlytics."""

from __future__ import annotations

import os
from datetime import datetime, timezone

try:
    import boto3
    from boto3.dynamodb.conditions import Attr, Key
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - boto3 only needed when AWS is used
    boto3 = None
    Key = None
    Attr = None
    ClientError = None

USERS_TABLE_NAME = os.getenv("ROWLYTICS_USERS_TABLE", "RowlyticsUsers")
TEAMS_TABLE_NAME = os.getenv("ROWLYTICS_TEAMS_TABLE", "RowlyticsTeams")
TEAM_MEMBERS_TABLE_NAME = os.getenv("ROWLYTICS_TEAM_MEMBERS_TABLE", "RowlyticsTeamMembers")
TEAM_MEMBERS_USER_INDEX = os.getenv("ROWLYTICS_TEAM_MEMBERS_USER_INDEX", "UserIdIndex")
TEAM_NAME_INDEX = os.getenv("ROWLYTICS_TEAMS_NAME_INDEX", "TeamNameIndex")
RECORDINGS_TABLE_NAME = os.getenv("ROWLYTICS_RECORDINGS_TABLE", "RowlyticsRecordings")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_resource():
    if boto3 is None:
        raise RuntimeError("boto3 is required for DynamoDB access")
    return boto3.resource("dynamodb")


def get_users_table():
    return _get_resource().Table(USERS_TABLE_NAME)


def get_team_members_table():
    return _get_resource().Table(TEAM_MEMBERS_TABLE_NAME)


def get_teams_table():
    return _get_resource().Table(TEAMS_TABLE_NAME)


def get_recordings_table():
    if not RECORDINGS_TABLE_NAME:
        raise RuntimeError("ROWLYTICS_RECORDINGS_TABLE is not configured")
    return _get_resource().Table(RECORDINGS_TABLE_NAME)


def get_ddb_tables():
    return get_users_table(), get_team_members_table()


def sync_user_profile(user_id: str | None, email: str | None, name: str | None) -> str | None:
    if not user_id:
        return name
    table = get_users_table()

    safe_name = name or (email.split("@")[0] if email else "New Rower")
    now = now_iso()

    update_expr = (
        "SET #name = if_not_exists(#name, :name), "
        "createdAt = if_not_exists(createdAt, :createdAt)"
    )
    expr_attr_names = {"#name": "name"}
    expr_attr_values = {":name": safe_name, ":createdAt": now}

    if email:
        update_expr += ", email = if_not_exists(email, :email)"
        expr_attr_values[":email"] = email

    try:
        response = table.update_item(
            Key={"userId": user_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW",
        )
    except Exception:
        return name

    attributes = response.get("Attributes") or {}
    return attributes.get("name") or name


def batch_get_users(users_table, user_ids):
    if not user_ids:
        return {}
    client = users_table.meta.client
    users_by_id = {}
    for idx in range(0, len(user_ids), 100):
        chunk = user_ids[idx:idx + 100]
        response = client.batch_get_item(
            RequestItems={
                users_table.name: {
                    "Keys": [{"userId": user_id} for user_id in chunk]
                }
            }
        )
        users = response.get("Responses", {}).get(users_table.name, [])
        for user in users:
            user_id = user.get("userId")
            if user_id:
                users_by_id[user_id] = user
    return users_by_id


def fetch_team_members(users_table, team_members_table, team_id: str, allowed_roles: set[str]):
    response = team_members_table.query(
        KeyConditionExpression=Key("teamId").eq(team_id)
    )
    items = response.get("Items", [])
    user_ids = [item.get("userId") for item in items if item.get("userId")]
    users_by_id = batch_get_users(users_table, user_ids)

    members = []
    for item in items:
        user_id = item.get("userId")
        user = users_by_id.get(user_id, {})
        raw_role = item.get("memberRole")
        role = raw_role.lower() if isinstance(raw_role, str) else "rower"
        if role not in allowed_roles:
            role = "coach" if "coach" in role else "rower"

        members.append({
            "userId": user_id,
            "memberRole": role,
            "joinedAt": item.get("joinedAt"),
            "name": user.get("name"),
            "email": user.get("email"),
        })

    return members


def get_team_membership(team_members_table, user_id: str):
    try:
        response = team_members_table.query(
            IndexName=TEAM_MEMBERS_USER_INDEX,
            KeyConditionExpression=Key("userId").eq(user_id),
        )
        items = response.get("Items", [])
        return items[0] if items else None
    except Exception as err:
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
            if error_code in {"ValidationException", "ResourceNotFoundException"}:
                if Attr is None:
                    raise
                response = team_members_table.scan(
                    FilterExpression=Attr("userId").eq(user_id),
                    Limit=1,
                )
                items = response.get("Items", [])
                return items[0] if items else None
        raise


def get_team(teams_table, team_id: str):
    response = teams_table.get_item(Key={"teamId": team_id})
    return response.get("Item")


def query_all(table, **kwargs):
    items = []
    last_key = None
    while True:
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
    return items


def scan_all(table, **kwargs):
    items = []
    last_key = None
    while True:
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
    return items


def list_team_memberships(team_members_table, user_id: str):
    try:
        return query_all(
            team_members_table,
            IndexName=TEAM_MEMBERS_USER_INDEX,
            KeyConditionExpression=Key("userId").eq(user_id),
        )
    except Exception as err:
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
            if error_code in {"ValidationException", "ResourceNotFoundException"}:
                if Attr is None:
                    raise
                return scan_all(
                    team_members_table,
                    FilterExpression=Attr("userId").eq(user_id),
                )
        raise


def list_team_members_by_team(team_members_table, team_id: str):
    return query_all(
        team_members_table,
        KeyConditionExpression=Key("teamId").eq(team_id),
    )


def list_owned_teams(teams_table, user_id: str):
    if Attr is None:
        return []
    return scan_all(
        teams_table,
        FilterExpression=Attr("coachUserId").eq(user_id),
    )


def list_recordings(recordings_table, user_id: str):
    return query_all(
        recordings_table,
        KeyConditionExpression=Key("userId").eq(user_id),
    )


def team_name_exists(teams_table, team_name: str) -> bool:
    if not team_name:
        return False

    if Attr is None:
        raise RuntimeError("boto3 is required for DynamoDB access")

    try:
        response = teams_table.query(
            IndexName=TEAM_NAME_INDEX,
            KeyConditionExpression=Key("teamName").eq(team_name),
            Limit=1,
        )
        if response.get("Items"):
            return True
    except Exception as err:
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
            if error_code not in {"ValidationException", "ResourceNotFoundException"}:
                raise
        else:
            raise

    response = teams_table.scan(
        FilterExpression=Attr("teamName").eq(team_name),
        Limit=1,
    )
    return bool(response.get("Items"))
