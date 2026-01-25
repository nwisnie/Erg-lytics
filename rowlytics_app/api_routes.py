"""API routes for Rowlytics."""

from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, jsonify, request, session

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - boto3 only needed when AWS is used
    ClientError = None

from rowlytics_app.auth.cognito import delete_cognito_user
from rowlytics_app.services.dynamodb import (
    fetch_team_members,
    get_ddb_tables,
    get_recordings_table,
    get_team,
    get_team_membership,
    get_teams_table,
    list_recordings,
    list_team_memberships,
    now_iso,
    team_name_exists,
)
from rowlytics_app.services.s3 import UPLOAD_BUCKET_NAME, get_s3_client

api_bp = Blueprint("api", __name__, url_prefix="/api")

ALLOWED_TEAM_ROLES = {"coach", "rower"}


@api_bp.route("/teams/<team_id>/members", methods=["GET"])
def list_team_members(team_id):
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    try:
        users_table, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        members = fetch_team_members(
            users_table,
            team_members_table,
            team_id,
            ALLOWED_TEAM_ROLES,
        )
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

    joined_at = data.get("joinedAt") or now_iso()

    try:
        users_table, team_members_table = get_ddb_tables()
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
        users_table, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        membership = get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to load team", "detail": str(err)}), 500

    if not membership:
        return jsonify({"teamId": None, "members": []})

    team_id = membership.get("teamId")
    try:
        members = fetch_team_members(
            users_table,
            team_members_table,
            team_id,
            ALLOWED_TEAM_ROLES,
        )
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

    joined_at = data.get("joinedAt") or now_iso()

    try:
        users_table, team_members_table = get_ddb_tables()
        teams_table = get_teams_table()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    team_item = get_team(teams_table, team_id)
    if not team_item:
        return jsonify({"error": "Team not found"}), 404

    try:
        existing = get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check current team", "detail": str(err)}), 500

    if existing and existing.get("teamId") != team_id:
        return jsonify({
            "error": "Already on a team. Leave your current team first.",
            "teamId": existing.get("teamId"),
        }), 409

    if existing and existing.get("teamId") == team_id:
        try:
            members = fetch_team_members(
                users_table,
                team_members_table,
                team_id,
                ALLOWED_TEAM_ROLES,
            )
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
        members = fetch_team_members(
            users_table,
            team_members_table,
            team_id,
            ALLOWED_TEAM_ROLES,
        )
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

    created_at = data.get("createdAt") or now_iso()

    try:
        users_table, team_members_table = get_ddb_tables()
        teams_table = get_teams_table()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        existing = get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check current team", "detail": str(err)}), 500

    if existing:
        return jsonify({
            "error": "Already on a team. Leave your current team first.",
            "teamId": existing.get("teamId"),
        }), 409

    try:
        if team_name_exists(teams_table, team_name):
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
        members = fetch_team_members(
            users_table,
            team_members_table,
            team_id,
            ALLOWED_TEAM_ROLES,
        )
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
        _, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        membership = get_team_membership(team_members_table, user_id)
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
        users_table, _ = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    update_expr = "SET #name = :name, updatedAt = :updatedAt"
    expr_attr_names = {"#name": "name"}
    expr_attr_values = {":name": name, ":updatedAt": now_iso()}

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
        users_table, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        delete_cognito_user(user_id, session.get("user_email"), session.get("access_token"))
    except Exception as err:
        return jsonify({"error": "Unable to delete Cognito user", "detail": str(err)}), 500

    recordings_table = None
    s3 = None
    try:
        recordings_table = get_recordings_table()
        s3 = get_s3_client()
    except RuntimeError:
        recordings_table = None
        s3 = None

    if recordings_table is not None:
        try:
            recordings = list_recordings(recordings_table, user_id)
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
        memberships = list_team_memberships(team_members_table, user_id)
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
        s3 = get_s3_client()
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
    created_at = data.get("createdAt") or now_iso()

    if not user_id or not object_key:
        return jsonify({"error": "userId and objectKey are required"}), 400

    try:
        recordings_table = get_recordings_table()
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
def list_recordings_for_user(user_id):
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        recordings_table = get_recordings_table()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        items = list_recordings(recordings_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to load recordings", "detail": str(err)}), 500
    try:
        s3 = get_s3_client()
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
