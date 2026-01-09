"""API routes for Rowlytics."""

import os
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, jsonify, request

try:
    import boto3
    from boto3.dynamodb.conditions import Key
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - boto3 only needed when AWS is used
    boto3 = None
    Key = None
    ClientError = None

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Database file stored next to this python file
DB_PATH = os.path.join(os.path.dirname(__file__), "visits.db")

# AWS resource names
# If the names change we can quickly update them here or change env vars
USERS_TABLE_NAME = os.getenv("ROWLYTICS_USERS_TABLE", "RowlyticsUsers")
TEAM_MEMBERS_TABLE_NAME = os.getenv("ROWLYTICS_TEAM_MEMBERS_TABLE", "RowlyticsTeamMembers")
RECORDINGS_TABLE_NAME = os.getenv("ROWLYTICS_RECORDINGS_TABLE", "RowlyticsRecordings")
UPLOAD_BUCKET_NAME = os.getenv("ROWLYTICS_UPLOAD_BUCKET", "rowlyticsuploads")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_ddb_tables():
    if boto3 is None or Key is None:
        raise RuntimeError("boto3 is required for DynamoDB access")
    dynamodb = boto3.resource("dynamodb")
    users_table = dynamodb.Table(USERS_TABLE_NAME)
    team_members_table = dynamodb.Table(TEAM_MEMBERS_TABLE_NAME)
    return users_table, team_members_table


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
        response = team_members_table.query(
            KeyConditionExpression=Key("teamId").eq(team_id)
        )
    except Exception as err:
        return jsonify({"error": "Unable to query team members", "detail": str(err)}), 500

    items = response.get("Items", [])
    user_ids = [item.get("userId") for item in items if item.get("userId")]
    users_by_id = {}

    try:
        users_by_id = _batch_get_users(users_table, user_ids)
    except Exception as err:
        return jsonify({"error": "Unable to load user details", "detail": str(err)}), 500

    members = []
    for item in items:
        user_id = item.get("userId")
        user = users_by_id.get(user_id, {})
        members.append({
            "userId": user_id,
            "memberRole": item.get("memberRole"),
            "status": item.get("status"),
            "joinedAt": item.get("joinedAt"),
            "name": user.get("name"),
            "email": user.get("email"),
        })

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
    status = (data.get("status") or "active").strip()
    joined_at = data.get("joinedAt") or _now_iso()

    try:
        _, team_members_table = _get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    item = {
        "teamId": team_id,
        "userId": user_id,
        "memberRole": member_role,
        "status": status,
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
