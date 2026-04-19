# Reference Rowlytics

## System Structure

- Rowlytics uses a Flask application served through AWS Lambda and API Gateway.
- `create_app()` initializes Flask, loads environment-based configuration, applies the auth gate, and registers the public and API blueprints.
- `public_bp` serves HTML routes.
- `api_bp` serves JSON endpoints under `/api`.
- AWS SAM defines the deployed backend resources: Lambda, API Gateway, DynamoDB, S3, and Cognito.

## Key APIs / Interfaces

### POST /api/recordings/presign

- Auth: Required
- Purpose: Returns a presigned S3 upload URL for a recording clip.
- Request fields:
  - `userId`
  - `contentType` (optional)
  - `durationSec` (optional, used to enforce the daily upload cap before S3 upload)
  - `createdAt` (optional, used to determine the UTC upload day)
- Response fields:
  - `uploadUrl`
  - `objectKey`
  - `bucket`
  - `expiresIn`
- Validation:
  - Recording uploads are capped at 2 hours total per user per UTC day.

### POST /api/workouts

- Auth: Required
- Purpose: Saves a completed workout summary.
- Required request field:
  - `durationSec`
- Optional request fields:
  - `summary`
  - `workoutScore`
  - `alignmentDetails`
  - `strokeCount`
  - `cadenceSpm`
  - `rangeOfMotion`
  - `dominantSide`
- Response fields:
  - `status`
  - `workoutId`

## Configuration

| Variable | Purpose |
|---|---|
| `ROWLYTICS_AUTH_REQUIRED` | Enables or disables auth enforcement |
| `ROWLYTICS_USERS_TABLE` | DynamoDB users table name |
| `ROWLYTICS_RECORDINGS_TABLE` | DynamoDB recordings table name |
| `ROWLYTICS_WORKOUTS_TABLE` | DynamoDB workouts table name |
| `ROWLYTICS_UPLOAD_BUCKET` | S3 upload bucket name |
| `ROWLYTICS_COGNITO_DOMAIN` | Cognito hosted UI domain |
| `ROWLYTICS_COGNITO_CLIENT_ID` | Cognito client ID |
| `ROWLYTICS_COGNITO_REDIRECT_URI` | Login callback URI |

## DB Schemas

### UsersTable

- Primary key: `userId`
- Common attributes:
  - `email`
  - `name`
  - `createdAt`
  - `updatedAt`
- Secondary index:
  - `EmailIndex(email)`

### WorkoutsTable

- Primary key:
  - Partition key: `userId`
  - Sort key: `workoutId`
- Common attributes:
  - `durationSec`
  - `workoutScore`
  - `summary`
  - `alignmentDetails`
  - `strokeCount`
  - `cadenceSpm`
  - `rangeOfMotion`
  - `dominantSide`
  - `createdAt`
  - `completedAt`
- Secondary index:
  - `UserCompletedAtIndex(userId, completedAt)`

## Project Specific Section 1

### Workout Alignment Analysis

- Input data is a list of landmark frames captured from the workout video.
- The system detects the dominant side of the rower.
- A movement gate checks whether enough rowing motion was captured.
- The alignment routine builds an ideal progression model from the clip.
- Output metrics include:
  - `strokeCount`
  - `cadenceSpm`
  - `rangeOfMotion`
  - `score`
  - `meanDistance`
  - `anchorLandmark`

## Project Specific Section 2

### Recording Upload Flow

- The browser requests a presigned upload URL from `/api/recordings/presign`.
- The video clip is uploaded directly to S3.
- Recording metadata is saved through `/api/recordings`.
- Both endpoints enforce a maximum of 2 uploaded recording hours per user per UTC day.
- Saved metadata includes:
  - `userId`
  - `recordingId`
  - `objectKey`
  - `contentType`
  - `durationSec`
  - `createdAt`
- Playback links are later generated from stored S3 object keys.

#### Gen AI Usage:
Gen AI was not used to write this documentation.
