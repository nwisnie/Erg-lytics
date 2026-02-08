# AWS Environment Variables

This document lists the AWS-related environment variables used by Rowlytics, their defaults, and where they are used. These can also be viewed on the console under our API Gateway

## Core Tables

- `ROWLYTICS_USERS_TABLE`
  - Default: `RowlyticsUsers`
  - Used by: `rowlytics_app/services/dynamodb.py`

- `ROWLYTICS_TEAMS_TABLE`
  - Default: `RowlyticsTeams`
  - Used by: `rowlytics_app/services/dynamodb.py`

- `ROWLYTICS_TEAM_MEMBERS_TABLE`
  - Default: `RowlyticsTeamMembers`
  - Used by: `rowlytics_app/services/dynamodb.py`

- `ROWLYTICS_RECORDINGS_TABLE`
  - Default: `RowlyticsRecordings`
  - Used by: `rowlytics_app/services/dynamodb.py`
  - Note: This is treated as required in the recordings helpers.

## DynamoDB Indexes

- `ROWLYTICS_TEAM_MEMBERS_USER_INDEX`
  - Default: `UserIdIndex`
  - Used by: `rowlytics_app/services/dynamodb.py`

- `ROWLYTICS_TEAMS_NAME_INDEX`
  - Default: `TeamNameIndex`
  - Used by: `rowlytics_app/services/dynamodb.py`

## S3

- `ROWLYTICS_UPLOAD_BUCKET`
  - Default: `rowlyticsuploads`
  - Used by: `rowlytics_app/services/s3.py`
  - Note: S3 helpers treat this as required and will error if missing.

## Cognito

- `ROWLYTICS_COGNITO_DOMAIN`
  - Default: `https://rowlytics-auth.auth.us-east-2.amazoncognito.com`
  - Used by: `rowlytics_app/__init__.py`, `rowlytics_app/auth/cognito.py`

- `ROWLYTICS_COGNITO_CLIENT_ID`
  - Default: `6na8lcnrau96407c76atn8641b`
  - Used by: `rowlytics_app/__init__.py`, `rowlytics_app/auth/cognito.py`

- `ROWLYTICS_COGNITO_REDIRECT_URI`
  - Default: `http://localhost:5000/auth/callback`
  - Used by: `rowlytics_app/__init__.py`, `rowlytics_app/auth/cognito.py`

- `ROWLYTICS_COGNITO_LOGOUT_REDIRECT_URI`
  - Default: `http://localhost:5000/signin`
  - Used by: `rowlytics_app/__init__.py`, `rowlytics_app/auth/cognito.py`

- `ROWLYTICS_COGNITO_USER_POOL_ID`
  - Default: empty string
  - Used by: `rowlytics_app/auth/cognito.py`
  - Note: Required for admin delete operations.

## Misc

- `ROWLYTICS_ENV`
  - Default: `development`
  - Used by: `rowlytics_app/__init__.py`, `rowlytics_app/logging_config.py`

- `ROWLYTICS_LOG_LEVEL`
  - Default: `INFO`
  - Used by: `rowlytics_app/logging_config.py`

- `ROWLYTICS_AUTH_REQUIRED`
  - Default: `true`
  - Used by: `rowlytics_app/__init__.py`

- `ROWLYTICS_CLOUDFRONT_DOMAIN`
  - Default: `d3oiecpdwfniky.cloudfront.net`
  - Used by: `rowlytics_app/__init__.py`

## Notes

- Defaults are intended for local development. In AWS, you should set all relevant values via Lambda environment variables or SAM parameters.
- If you change table or index names in `backend/template.yaml`, update the corresponding env vars.
