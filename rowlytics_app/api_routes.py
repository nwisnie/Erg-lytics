"""API routes for Rowlytics."""

import os
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, jsonify, request, session

try:
    import boto3
    from boto3.dynamodb.conditions import Attr, Key
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - boto3 only needed when AWS is used
    boto3 = None
    Key = None
    Attr = None
    ClientError = None

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Database file stored next to this python file
DB_PATH = os.path.join(os.path.dirname(__file__), "visits.db")

# AWS resource names
# If the names change we can quickly update them here or change env vars
USERS_TABLE_NAME = os.getenv("ROWLYTICS_USERS_TABLE", "RowlyticsUsers")
TEAMS_TABLE_NAME = os.getenv("ROWLYTICS_TEAMS_TABLE", "RowlyticsTeams")
TEAM_MEMBERS_TABLE_NAME = os.getenv("ROWLYTICS_TEAM_MEMBERS_TABLE", "RowlyticsTeamMembers")
TEAM_MEMBERS_USER_INDEX = os.getenv("ROWLYTICS_TEAM_MEMBERS_USER_INDEX", "UserIdIndex")
TEAM_NAME_INDEX = os.getenv("ROWLYTICS_TEAMS_NAME_INDEX", "TeamNameIndex")
RECORDINGS_TABLE_NAME = os.getenv("ROWLYTICS_RECORDINGS_TABLE", "RowlyticsRecordings")
UPLOAD_BUCKET_NAME = os.getenv("ROWLYTICS_UPLOAD_BUCKET", "rowlyticsuploads")
COGNITO_USER_POOL_ID = os.getenv("ROWLYTICS_COGNITO_USER_POOL_ID", "")

ALLOWED_TEAM_ROLES = {"coach", "rower"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_ddb_tables():
    if boto3 is None or Key is None:
        raise RuntimeError("boto3 is required for DynamoDB access")
    dynamodb = boto3.resource("dynamodb")
    users_table = dynamodb.Table(USERS_TABLE_NAME)
    team_members_table = dynamodb.Table(TEAM_MEMBERS_TABLE_NAME)
    return users_table, team_members_table


def _get_teams_table():
    if boto3 is None:
        raise RuntimeError("boto3 is required for DynamoDB access")
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TEAMS_TABLE_NAME)


def _get_recordings_table():
    if boto3 is None or Key is None:
        raise RuntimeError("boto3 is required for DynamoDB access")
    if not RECORDINGS_TABLE_NAME:
        raise RuntimeError("ROWLYTICS_RECORDINGS_TABLE is not configured")
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(RECORDINGS_TABLE_NAME)


def _get_s3_client():
    if boto3 is None:
        raise RuntimeError("boto3 is required for S3 access")
    if not UPLOAD_BUCKET_NAME:
        raise RuntimeError("ROWLYTICS_UPLOAD_BUCKET is not configured")
    return boto3.client("s3")


def _get_cognito_client():
    if boto3 is None:
        raise RuntimeError("boto3 is required for Cognito access")
    return boto3.client("cognito-idp")


def _delete_cognito_user(user_id: str, email: str | None, access_token: str | None):
    client = _get_cognito_client()
    last_error = None

    if access_token:
        try:
            client.delete_user(AccessToken=access_token)
            return
        except Exception as err:
            last_error = err

    username = email or user_id
    if not COGNITO_USER_POOL_ID or not username:
        raise RuntimeError("Missing Cognito pool id or username")

    try:
        client.admin_delete_user(UserPoolId=COGNITO_USER_POOL_ID, Username=username)
        return
    except Exception as err:
        last_error = err

    raise RuntimeError(str(last_error) if last_error else "Unable to delete Cognito user")


def _batch_get_users(users_table, user_ids):
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


def _fetch_team_members(users_table, team_members_table, team_id: str):
    response = team_members_table.query(
        KeyConditionExpression=Key("teamId").eq(team_id)
    )
    items = response.get("Items", [])
    user_ids = [item.get("userId") for item in items if item.get("userId")]
    users_by_id = _batch_get_users(users_table, user_ids)

    members = []
    for item in items:
        user_id = item.get("userId")
        user = users_by_id.get(user_id, {})
        raw_role = item.get("memberRole")
        role = raw_role.lower() if isinstance(raw_role, str) else "rower"
        if role not in ALLOWED_TEAM_ROLES:
            role = "coach" if "coach" in role else "rower"

        members.append({
            "userId": user_id,
            "memberRole": role,
            "joinedAt": item.get("joinedAt"),
            "name": user.get("name"),
            "email": user.get("email"),
        })

    return members


def _get_team_membership(team_members_table, user_id: str):
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


def _get_team(teams_table, team_id: str):
    response = teams_table.get_item(Key={"teamId": team_id})
    return response.get("Item")


def _query_all(table, **kwargs):
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


def _scan_all(table, **kwargs):
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


def _list_team_memberships(team_members_table, user_id: str):
    try:
        return _query_all(
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
                return _scan_all(
                    team_members_table,
                    FilterExpression=Attr("userId").eq(user_id),
                )
        raise


def _list_team_members_by_team(team_members_table, team_id: str):
    return _query_all(
        team_members_table,
        KeyConditionExpression=Key("teamId").eq(team_id),
    )


def _list_owned_teams(teams_table, user_id: str):
    if Attr is None:
        return []
    return _scan_all(
        teams_table,
        FilterExpression=Attr("coachUserId").eq(user_id),
    )


def _list_recordings(recordings_table, user_id: str):
    return _query_all(
        recordings_table,
        KeyConditionExpression=Key("userId").eq(user_id),
    )


def _team_name_exists(teams_table, team_name: str) -> bool:
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


def increment_page(slug: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Make sure the table exists
    c.execute("""
        CREATE TABLE IF NOT EXISTS page_visits (
            slug TEXT PRIMARY KEY,
            count INTEGER NOT NULL
        )
    """)

    # Increment or insert row
    c.execute("""
        INSERT INTO page_visits (slug, count)
        VALUES (?, 1)
        ON CONFLICT(slug) DO UPDATE SET count = count + 1
    """, (slug,))

    conn.commit()
    conn.close()


@api_bp.route("/increment/<slug>", methods=["POST"])
def increment(slug):
    increment_page(slug)
    return jsonify({"status": "ok"})


@api_bp.route("/count/<slug>")
def get_count(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count FROM page_visits WHERE slug = ?", (slug,))
    row = c.fetchone()
    conn.close()
    return jsonify({"count": row[0] if row else 0})


@api_bp.route("/teams/<team_id>/members", methods=["GET"])
def list_team_members(team_id):
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    try:
        users_table, team_members_table = _get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        members = _fetch_team_members(users_table, team_members_table, team_id)
    except Exception as err:
        return jsonify({"error": "Unable to query team members", "detail": str(err)}), 500

    return jsonify({"teamId": team_id, "members": members})


@api_bp.route("/teams/<team_id>/members", methods=["POST"])
def add_team_member(team_id):
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    data = request.get_json(silent=True) or {}
    user_id = (data.get("userId") or "").strip()
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    member_role = (data.get("memberRole") or "rower").strip()
    member_role = member_role.lower()
    if member_role not in ALLOWED_TEAM_ROLES:
        return jsonify({"error": "memberRole must be coach or rower"}), 400

    joined_at = data.get("joinedAt") or _now_iso()

    try:
        users_table, team_members_table = _get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        user_response = users_table.get_item(Key={"userId": user_id})
    except Exception as err:
        return jsonify({"error": "Unable to verify user", "detail": str(err)}), 500

    if not user_response.get("Item"):
        return jsonify({"error": "User does not exist"}), 404

    item = {
        "teamId": team_id,
        "userId": user_id,
        "memberRole": member_role,
        "joinedAt": joined_at,
    }

    try:
        team_members_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(teamId) AND attribute_not_exists(userId)",
        )
    except Exception as err:
        error_code = None
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
        if error_code == "ConditionalCheckFailedException":
            return jsonify({"error": "User already on team"}), 409
        return jsonify({"error": "Unable to add team member", "detail": str(err)}), 500

    return jsonify({"status": "ok", "teamId": team_id, "userId": user_id}), 201


@api_bp.route("/team/current", methods=["GET"])
def current_team():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    try:
        users_table, team_members_table = _get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        membership = _get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to load team", "detail": str(err)}), 500

    if not membership:
        return jsonify({"teamId": None, "members": []})

    team_id = membership.get("teamId")
    try:
        members = _fetch_team_members(users_table, team_members_table, team_id)
    except Exception as err:
        return jsonify({"error": "Unable to load team members", "detail": str(err)}), 500

    return jsonify({
        "teamId": team_id,
        "members": members,
        "memberRole": membership.get("memberRole"),
    })


@api_bp.route("/team/join", methods=["POST"])
def join_team():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    team_id = (data.get("teamId") or "").strip()
    if not team_id:
        return jsonify({"error": "teamId is required"}), 400

    member_role = (data.get("memberRole") or "rower").strip().lower()
    if member_role not in ALLOWED_TEAM_ROLES:
        return jsonify({"error": "memberRole must be coach or rower"}), 400

    joined_at = data.get("joinedAt") or _now_iso()

    try:
        users_table, team_members_table = _get_ddb_tables()
        teams_table = _get_teams_table()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    team_item = _get_team(teams_table, team_id)
    if not team_item:
        return jsonify({"error": "Team not found"}), 404

    try:
        existing = _get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check current team", "detail": str(err)}), 500

    if existing and existing.get("teamId") != team_id:
        return jsonify({
            "error": "Already on a team. Leave your current team first.",
            "teamId": existing.get("teamId"),
        }), 409

    if existing and existing.get("teamId") == team_id:
        try:
            members = _fetch_team_members(users_table, team_members_table, team_id)
        except Exception as err:
            return jsonify({"error": "Unable to load team members", "detail": str(err)}), 500
        return jsonify({"status": "ok", "teamId": team_id, "members": members})

    if not existing:
        item = {
            "teamId": team_id,
            "userId": user_id,
            "memberRole": member_role,
            "joinedAt": joined_at,
        }
        try:
            team_members_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(teamId) AND attribute_not_exists(userId)",
            )
        except Exception as err:
            error_code = None
            if ClientError and isinstance(err, ClientError):
                error_code = err.response.get("Error", {}).get("Code")
            if error_code != "ConditionalCheckFailedException":
                return jsonify({"error": "Unable to join team", "detail": str(err)}), 500

    try:
        members = _fetch_team_members(users_table, team_members_table, team_id)
    except Exception as err:
        return jsonify({"error": "Unable to load team members", "detail": str(err)}), 500

    return jsonify({"status": "ok", "teamId": team_id, "members": members})


@api_bp.route("/team/create", methods=["POST"])
def create_team():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    team_name = (data.get("teamName") or "").strip()
    if not team_name:
        return jsonify({"error": "teamName is required"}), 400

    created_at = data.get("createdAt") or _now_iso()

    try:
        users_table, team_members_table = _get_ddb_tables()
        teams_table = _get_teams_table()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        existing = _get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check current team", "detail": str(err)}), 500

    if existing:
        return jsonify({
            "error": "Already on a team. Leave your current team first.",
            "teamId": existing.get("teamId"),
        }), 409

    try:
        if _team_name_exists(teams_table, team_name):
            return jsonify({"error": "Team name already exists"}), 409
    except Exception as err:
        return jsonify({"error": "Unable to check team name", "detail": str(err)}), 500

    team_id = uuid4().hex
    team_item = {
        "teamId": team_id,
        "teamName": team_name,
        "coachUserId": user_id,
        "createdAt": created_at,
    }

    try:
        teams_table.put_item(
            Item=team_item,
            ConditionExpression="attribute_not_exists(teamId)",
        )
    except Exception as err:
        return jsonify({"error": "Unable to create team", "detail": str(err)}), 500

    member_item = {
        "teamId": team_id,
        "userId": user_id,
        "memberRole": "coach",
        "joinedAt": created_at,
    }

    try:
        team_members_table.put_item(
            Item=member_item,
            ConditionExpression="attribute_not_exists(teamId) AND attribute_not_exists(userId)",
        )
    except Exception as err:
        return jsonify({"error": "Unable to add team owner", "detail": str(err)}), 500

    try:
        members = _fetch_team_members(users_table, team_members_table, team_id)
    except Exception as err:
        return jsonify({"error": "Unable to load team members", "detail": str(err)}), 500

    return jsonify({
        "status": "ok",
        "teamId": team_id,
        "teamName": team_name,
        "members": members,
    }), 201


@api_bp.route("/team/leave", methods=["DELETE"])
def leave_team():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    try:
        _, team_members_table = _get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        membership = _get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check current team", "detail": str(err)}), 500

    if not membership:
        return jsonify({"error": "User is not on a team"}), 404

    team_id = membership.get("teamId")
    try:
        team_members_table.delete_item(Key={"teamId": team_id, "userId": user_id})
    except Exception as err:
        return jsonify({"error": "Unable to leave team", "detail": str(err)}), 500

    return jsonify({"status": "ok", "teamId": team_id})


@api_bp.route("/account/name", methods=["POST"])
def update_account_name():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        users_table, _ = _get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    update_expr = "SET #name = :name, updatedAt = :updatedAt"
    expr_attr_names = {"#name": "name"}
    expr_attr_values = {":name": name, ":updatedAt": _now_iso()}

    user_email = session.get("user_email")
    if user_email:
        update_expr += ", email = if_not_exists(email, :email)"
        expr_attr_values[":email"] = user_email

    try:
        users_table.update_item(
            Key={"userId": user_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )
    except Exception as err:
        return jsonify({"error": "Unable to update name", "detail": str(err)}), 500

    session["user_name"] = name
    return jsonify({"status": "ok", "name": name})


@api_bp.route("/account/delete", methods=["POST"])
def delete_account():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    try:
        users_table, team_members_table = _get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        _delete_cognito_user(user_id, session.get("user_email"), session.get("access_token"))
    except Exception as err:
        return jsonify({"error": "Unable to delete Cognito user", "detail": str(err)}), 500

    recordings_table = None
    s3 = None
    try:
        recordings_table = _get_recordings_table()
        s3 = _get_s3_client()
    except RuntimeError:
        recordings_table = None
        s3 = None

    if recordings_table is not None:
        try:
            recordings = _list_recordings(recordings_table, user_id)
        except Exception as err:
            return jsonify({"error": "Unable to load recordings", "detail": str(err)}), 500

        for item in recordings:
            recording_id = item.get("recordingId")
            object_key = item.get("objectKey")
            if s3 and object_key:
                try:
                    s3.delete_object(Bucket=UPLOAD_BUCKET_NAME, Key=object_key)
                except Exception:
                    pass
            if recording_id:
                recordings_table.delete_item(Key={"userId": user_id, "recordingId": recording_id})

    try:
        memberships = _list_team_memberships(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to load team memberships", "detail": str(err)}), 500

    for membership in memberships:
        team_id = membership.get("teamId")
        if team_id:
            team_members_table.delete_item(Key={"teamId": team_id, "userId": user_id})

    try:
        users_table.delete_item(Key={"userId": user_id})
    except Exception as err:
        return jsonify({"error": "Unable to delete user", "detail": str(err)}), 500

    session.clear()
    return jsonify({"status": "ok"})


@api_bp.route("/recordings/presign", methods=["POST"])
def presign_recording_upload():
    data = request.get_json(silent=True) or {}
    user_id = (data.get("userId") or "").strip()
    content_type = (data.get("contentType") or "video/webm").strip()

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        s3 = _get_s3_client()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    recording_id = uuid4().hex
    extension = "webm" if "webm" in content_type else "bin"
    object_key = f"recordings/{user_id}/{timestamp}-{recording_id}.{extension}"

    try:
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": UPLOAD_BUCKET_NAME,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=900,
        )
    except Exception as err:
        return jsonify({"error": "Unable to create upload URL", "detail": str(err)}), 500

    return jsonify({
        "uploadUrl": upload_url,
        "objectKey": object_key,
        "bucket": UPLOAD_BUCKET_NAME,
        "expiresIn": 900,
    })


@api_bp.route("/recordings", methods=["POST"])
def save_recording_metadata():
    data = request.get_json(silent=True) or {}
    user_id = (data.get("userId") or "").strip()
    object_key = (data.get("objectKey") or "").strip()
    content_type = (data.get("contentType") or "video/webm").strip()
    duration_sec = data.get("durationSec")
    created_at = data.get("createdAt") or _now_iso()

    if not user_id or not object_key:
        return jsonify({"error": "userId and objectKey are required"}), 400

    try:
        recordings_table = _get_recordings_table()
    except RuntimeError as err:
        return jsonify({"status": "skipped", "reason": str(err)}), 200

    recording_id = uuid4().hex
    item = {
        "userId": user_id,
        "recordingId": recording_id,
        "objectKey": object_key,
        "contentType": content_type,
        "durationSec": duration_sec,
        "createdAt": created_at,
    }

    try:
        recordings_table.put_item(Item=item)
    except Exception as err:
        return jsonify({"error": "Unable to save recording metadata", "detail": str(err)}), 500

    return jsonify({"status": "ok", "recordingId": recording_id})


@api_bp.route("/recordings/<user_id>", methods=["GET"])
def list_recordings(user_id):
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        recordings_table = _get_recordings_table()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        response = recordings_table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )
    except Exception as err:
        return jsonify({"error": "Unable to load recordings", "detail": str(err)}), 500

    items = response.get("Items", [])
    try:
        s3 = _get_s3_client()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    for item in items:
        object_key = item.get("objectKey")
        if object_key:
            item["playbackUrl"] = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": UPLOAD_BUCKET_NAME, "Key": object_key},
                ExpiresIn=900,
            )

    return jsonify({"userId": user_id, "recordings": items})
