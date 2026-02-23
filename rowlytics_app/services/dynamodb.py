"""DynamoDB helpers for Rowlytics."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

USERS_TABLE_NAME = os.getenv("ROWLYTICS_USERS_TABLE", "RowlyticsUsers")
TEAMS_TABLE_NAME = os.getenv("ROWLYTICS_TEAMS_TABLE", "RowlyticsTeams")
TEAM_MEMBERS_TABLE_NAME = os.getenv("ROWLYTICS_TEAM_MEMBERS_TABLE", "RowlyticsTeamMembers")
TEAM_MEMBERS_USER_INDEX = os.getenv("ROWLYTICS_TEAM_MEMBERS_USER_INDEX", "UserIdIndex")
TEAM_NAME_INDEX = os.getenv("ROWLYTICS_TEAMS_NAME_INDEX", "TeamNameIndex")
RECORDINGS_TABLE_NAME = os.getenv("ROWLYTICS_RECORDINGS_TABLE", "RowlyticsRecordings")
WORKOUTS_TABLE_NAME = os.getenv("ROWLYTICS_WORKOUTS_TABLE", "RowlyticsWorkouts")
LANDMARKS_TABLE_NAME = os.getenv("ROWLYTICS_LANDMARKS_TABLE", "RowlyticsLandmarks")
RECORDINGS_CREATED_AT_INDEX = os.getenv(
    "ROWLYTICS_RECORDINGS_CREATED_AT_INDEX",
    "UserCreatedAtIndex",
)
WORKOUTS_COMPLETED_AT_INDEX = os.getenv(
    "ROWLYTICS_WORKOUTS_COMPLETED_AT_INDEX",
    "UserCompletedAtIndex",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_resource():
    if boto3 is None:
        raise RuntimeError("boto3 is required for DynamoDB access")
    logger.debug("Creating DynamoDB resource")
    return boto3.resource("dynamodb")


def get_users_table():
    logger.debug(f"Accessing users table: {USERS_TABLE_NAME}")
    return _get_resource().Table(USERS_TABLE_NAME)


def get_team_members_table():
    logger.debug(f"Accessing team members table: {TEAM_MEMBERS_TABLE_NAME}")
    return _get_resource().Table(TEAM_MEMBERS_TABLE_NAME)


def get_teams_table():
    logger.debug(f"Accessing teams table: {TEAMS_TABLE_NAME}")
    return _get_resource().Table(TEAMS_TABLE_NAME)


def get_recordings_table():
    if not RECORDINGS_TABLE_NAME:
        logger.error("ROWLYTICS_RECORDINGS_TABLE environment variable is not configured")
        raise RuntimeError("ROWLYTICS_RECORDINGS_TABLE is not configured")
    logger.debug(f"Accessing recordings table: {RECORDINGS_TABLE_NAME}")
    return _get_resource().Table(RECORDINGS_TABLE_NAME)


def get_workouts_table():
    if not WORKOUTS_TABLE_NAME:
        logger.error("ROWLYTICS_WORKOUTS_TABLE environment variable is not configured")
        raise RuntimeError("ROWLYTICS_WORKOUTS_TABLE is not configured")
    logger.debug(f"Accessing workouts table: {WORKOUTS_TABLE_NAME}")
    return _get_resource().Table(WORKOUTS_TABLE_NAME)


def get_landmarks_table():
    if not LANDMARKS_TABLE_NAME:
        logger.error("ROWLYTICS_LANDMARKS_TABLE environment variable is not configured")
        raise RuntimeError("ROWLYTICS_LANDMARKS_TABLE is not configured")
    logger.debug(f"Accessing landmarks table: {LANDMARKS_TABLE_NAME}")
    return _get_resource().Table(LANDMARKS_TABLE_NAME)


def get_ddb_tables():
    return get_users_table(), get_team_members_table(), get_landmarks_table()


def sync_user_profile(user_id: str | None, email: str | None, name: str | None) -> str | None:
    if not user_id:
        logger.debug("sync_user_profile: no user_id provided")
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
        logger.debug(
            "sync_user_profile: updating user %s with name=%s, email=%s",
            user_id,
            safe_name,
            email,
        )
        response = table.update_item(
            Key={"userId": user_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW",
        )
        logger.info(f"sync_user_profile: successfully updated user {user_id}")
    except Exception as e:
        logger.error(
            "sync_user_profile: failed to update user %s: %s",
            user_id,
            e,
            exc_info=True,
        )
        return name

    attributes = response.get("Attributes") or {}
    return attributes.get("name") or name


def batch_get_users(users_table, user_ids):
    if not user_ids:
        logger.debug("batch_get_users: no user_ids provided")
        return {}
    client = users_table.meta.client
    users_by_id = {}
    logger.debug(f"batch_get_users: fetching {len(user_ids)} users")
    for idx in range(0, len(user_ids), 100):
        chunk = user_ids[idx:idx + 100]
        try:
            response = client.batch_get_item(
                RequestItems={
                    users_table.name: {
                        "Keys": [{"userId": user_id} for user_id in chunk]
                    }
                }
            )
            users = response.get("Responses", {}).get(users_table.name, [])
            logger.debug(f"batch_get_users: retrieved {len(users)} users in batch")
            for user in users:
                user_id = user.get("userId")
                if user_id:
                    users_by_id[user_id] = user
        except Exception as e:
            logger.error(
                "batch_get_users: failed to fetch batch of %d users: %s",
                len(chunk),
                e,
                exc_info=True,
            )
            raise
    logger.info(f"batch_get_users: successfully fetched {len(users_by_id)} total users")
    return users_by_id


def fetch_team_members(users_table, team_members_table, team_id: str, allowed_roles: set[str]):
    logger.debug(f"fetch_team_members: querying team {team_id}")
    try:
        response = team_members_table.query(
            KeyConditionExpression=Key("teamId").eq(team_id)
        )
        items = response.get("Items", [])
        logger.info(f"fetch_team_members: found {len(items)} team members for team {team_id}")
    except Exception as e:
        logger.error(
            "fetch_team_members: failed to query team members for team %s: %s",
            team_id,
            e,
            exc_info=True,
        )
        raise

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

    logger.debug(f"fetch_team_members: successfully built member list with {len(members)} members")
    return members


def get_team_membership(team_members_table, user_id: str):
    logger.debug(f"get_team_membership: querying membership for user {user_id}")
    try:
        response = team_members_table.query(
            IndexName=TEAM_MEMBERS_USER_INDEX,
            KeyConditionExpression=Key("userId").eq(user_id),
        )
        items = response.get("Items", [])
        if items:
            logger.info(f"get_team_membership: found membership for user {user_id}")
            return items[0]
        else:
            logger.info(f"get_team_membership: no membership found for user {user_id}")
            return None
    except Exception as err:
        logger.warning(f"get_team_membership: query failed, attempting fallback scan: {err}")
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
            if error_code in {"ValidationException", "ResourceNotFoundException"}:
                if Attr is None:
                    raise
                logger.debug(f"get_team_membership: using scan fallback for user {user_id}")
                response = team_members_table.scan(
                    FilterExpression=Attr("userId").eq(user_id),
                    Limit=1,
                )
                items = response.get("Items", [])
                return items[0] if items else None
        raise


def get_team(teams_table, team_id: str):
    logger.debug(f"get_team: fetching team {team_id}")
    try:
        response = teams_table.get_item(Key={"teamId": team_id})
        item = response.get("Item")
        if item:
            logger.info(f"get_team: successfully retrieved team {team_id}")
        else:
            logger.warning(f"get_team: team {team_id} not found")
        return item
    except Exception as e:
        logger.error(f"get_team: failed to fetch team {team_id}: {e}", exc_info=True)
        raise


def query_all(table, **kwargs):
    items = []
    last_key = None
    batch_count = 0
    while True:
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        try:
            response = table.query(**kwargs)
            batch_items = response.get("Items", [])
            items.extend(batch_items)
            batch_count += 1
            logger.debug(f"query_all: fetched {len(batch_items)} items in batch {batch_count}")
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
        except Exception as e:
            logger.error(f"query_all: failed during batch {batch_count}: {e}", exc_info=True)
            raise
    logger.info(f"query_all: retrieved {len(items)} total items across {batch_count} batches")
    return items


def query_page(table, *, limit: int, exclusive_start_key=None, **kwargs):
    query_kwargs = dict(kwargs)
    query_kwargs["Limit"] = limit
    if exclusive_start_key:
        query_kwargs["ExclusiveStartKey"] = exclusive_start_key
    response = table.query(**query_kwargs)
    return response.get("Items", []), response.get("LastEvaluatedKey")


def scan_all(table, **kwargs):
    items = []
    last_key = None
    batch_count = 0
    while True:
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        try:
            response = table.scan(**kwargs)
            batch_items = response.get("Items", [])
            items.extend(batch_items)
            batch_count += 1
            logger.debug(f"scan_all: fetched {len(batch_items)} items in batch {batch_count}")
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
        except Exception as e:
            logger.error(f"scan_all: failed during batch {batch_count}: {e}", exc_info=True)
            raise
    logger.info(f"scan_all: retrieved {len(items)} total items across {batch_count} batches")
    return items


def list_team_memberships(team_members_table, user_id: str):
    logger.debug(f"list_team_memberships: querying memberships for user {user_id}")
    try:
        items = query_all(
            team_members_table,
            IndexName=TEAM_MEMBERS_USER_INDEX,
            KeyConditionExpression=Key("userId").eq(user_id),
        )
        logger.info(
            "list_team_memberships: found %d team memberships for user %s",
            len(items),
            user_id,
        )
        return items
    except Exception as err:
        logger.warning(f"list_team_memberships: query failed, attempting fallback scan: {err}")
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
            if error_code in {"ValidationException", "ResourceNotFoundException"}:
                if Attr is None:
                    raise
                logger.debug(f"list_team_memberships: using scan fallback for user {user_id}")
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
    try:
        return query_all(
            recordings_table,
            IndexName=RECORDINGS_CREATED_AT_INDEX,
            KeyConditionExpression=Key("userId").eq(user_id),
            ScanIndexForward=False,
        )
    except Exception as err:
        logger.warning("list_recordings: index query failed, using fallback query: %s", err)
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
            if error_code not in {"ValidationException", "ResourceNotFoundException"}:
                raise
        else:
            raise

        items = query_all(
            recordings_table,
            KeyConditionExpression=Key("userId").eq(user_id),
        )
        return sorted(items, key=lambda item: item.get("createdAt") or "", reverse=True)


def list_recordings_page(recordings_table, user_id: str, limit: int, exclusive_start_key=None):
    return query_page(
        recordings_table,
        IndexName=RECORDINGS_CREATED_AT_INDEX,
        KeyConditionExpression=Key("userId").eq(user_id),
        ScanIndexForward=False,
        limit=limit,
        exclusive_start_key=exclusive_start_key,
    )


def list_workouts(workouts_table, user_id: str):
    try:
        return query_all(
            workouts_table,
            IndexName=WORKOUTS_COMPLETED_AT_INDEX,
            KeyConditionExpression=Key("userId").eq(user_id),
            ScanIndexForward=False,
        )
    except Exception as err:
        logger.warning("list_workouts: index query failed, using fallback query: %s", err)
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
            if error_code not in {"ValidationException", "ResourceNotFoundException"}:
                raise
        else:
            raise

        items = query_all(
            workouts_table,
            KeyConditionExpression=Key("userId").eq(user_id),
        )
        return sorted(
            items,
            key=lambda item: item.get("completedAt") or item.get("createdAt") or "",
            reverse=True,
        )


def list_workouts_page(workouts_table, user_id: str, limit: int, exclusive_start_key=None):
    return query_page(
        workouts_table,
        IndexName=WORKOUTS_COMPLETED_AT_INDEX,
        KeyConditionExpression=Key("userId").eq(user_id),
        ScanIndexForward=False,
        limit=limit,
        exclusive_start_key=exclusive_start_key,
    )


def fetch_team_members_page(
    users_table,
    team_members_table,
    team_id: str,
    allowed_roles: set[str],
    limit: int,
    exclusive_start_key=None,
):
    query_kwargs = {
        "KeyConditionExpression": Key("teamId").eq(team_id),
        "Limit": limit,
    }
    if exclusive_start_key:
        query_kwargs["ExclusiveStartKey"] = exclusive_start_key

    response = team_members_table.query(
        **query_kwargs,
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
    return members, response.get("LastEvaluatedKey")


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
