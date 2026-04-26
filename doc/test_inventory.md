# Rowlytics Test Inventory

Last updated: 2026-04-25

This document inventories the tests currently present in the repository. Automated tests live under `tests/` and `playwright/tests/`. Manual test artifacts live under `tests/test_documentation/`.

## Current Automated Test Suites

| Suite | Framework | Test count | Focus |
| --- | --- | ---: | --- |
| `tests/test_alignment.py` | `pytest` | 23 | Practice-stroke assembly, progression-step generation, progression matching, and ideal-model coordinate selection |
| `tests/test_angles.py` | `pytest` | 2 | Normalized joint-angle calculation and zero-length segment validation |
| `tests/test_app.py` | `pytest` | 8 | Flask app creation, core route rendering, auth URL integration, and static asset availability |
| `tests/test_auth.py` | `pytest` | 20 | Cognito token parsing, login URL generation, token exchange, token expiry, user deletion, and session helpers |
| `tests/test_deviation.py` | `pytest` | 26 | Skeletal deviation math helpers, limb/torso deviation scoring, midpoint handling, and full pose comparison |
| `tests/test_display_name_flow.py` | `pytest` | 6 | Display-name onboarding, auth callback redirects, gated navigation, and account-name updates |
| `tests/test_dynamodb.py` | `pytest` | 50 | DynamoDB resource/table access, profile sync, memberships, recordings, name uniqueness, and identifier resolution |
| `tests/test_email_integration.py` | `pytest` | 1 | End-to-end `/test-email` route integration with the mock email pipeline |
| `tests/test_email_routes.py` | `pytest` | 3 | `/test-email` route behavior for missing config, success, and failure paths |
| `tests/test_lambda.py` | `pytest` | 4 | Lambda adapter behavior and API Gateway stage-prefix header injection |
| `tests/test_mock_email.py` | `pytest` | 4 | Mock email composition, default-name fallback, content generation, and send-error propagation |
| `tests/test_recordings_api.py` | `pytest` | 3 | Recording upload guardrails, daily duration limits, and metadata normalization |
| `tests/test_s3.py` | `pytest` | 3 | S3 client initialization and required configuration checks |
| `tests/test_workout_api.py` | `pytest` | 8 | Workout validation, score persistence, team summary aggregation, and posture scoring helpers |
| `playwright/tests/a11y.spec.js` | `Playwright + axe-core` | 2 | Accessibility baseline checks for `/` and `/signin` |

Current automated inventory total: 163 tests

- Pytest total: 161 tests
- Playwright total: 2 tests

## Pytest Inventory

### `tests/conftest.py`

Shared pytest bootstrap only. It inserts the project root into `sys.path` so tests can import the app package when run directly.

### `tests/test_alignment.py` (23 tests)

This suite covers `PracticeStrokeAssembler` behavior:

- initialization defaults
- practice-stroke accumulation and `"finished"` handling
- progression-step generation and interval validation
- progression matching against current coordinates
- ideal coordinate-set selection for the closest progression step

### `tests/test_angles.py` (2 tests)

This suite covers `normalized_joint_angle()`:

- expected normalized output for a right-angle joint
- rejection of zero-length segments

### `tests/test_app.py` (8 tests)

This suite provides Flask smoke coverage for:

- `create_app()` returning a configured Flask instance
- landing-page rendering
- template detail route rendering
- unknown-route handling
- root `POST` rejection
- Cognito login URL integration
- `/signin` rendering
- static stylesheet serving

### `tests/test_auth.py` (20 tests)

This suite covers authentication helpers in `rowlytics_app.auth.cognito` and `rowlytics_app.auth.sessions`:

- JWT payload decoding success and failure cases
- Cognito login URL generation with valid and missing config
- OAuth token exchange request construction and response parsing
- token-expiry validation
- Cognito client creation
- user lookup helper behavior
- delete-user flows using access-token and admin-delete fallback paths
- Flask session context extraction

### `tests/test_deviation.py` (26 tests)

This suite covers `SkeletalDeviationCalculator` behavior:

- point validation and vector math helpers
- angle, joint-angle, segment-orientation, and angle-difference calculations
- arm, leg, and torso deviation scoring
- midpoint generation and named-coordinate maps
- full pose comparison across left arm, right arm, left leg, right leg, and torso
- midpoint fallback when center points are missing
- explicit center-point precedence when centers are present
- failure behavior when required body parts are missing or zero-length segments are supplied

### `tests/test_display_name_flow.py` (6 tests)

This suite covers the display-name onboarding flow:

- auth callback redirecting new users to `/display-name`
- auth callback redirecting established users to `/`
- session-gated users being forced through display-name setup
- `/display-name` remaining accessible while gated
- duplicate display-name rejection for `/api/account/name`
- successful account-name updates clearing the onboarding flag and updating session state

### `tests/test_dynamodb.py` (50 tests)

This suite covers DynamoDB-related helpers in `rowlytics_app.services.dynamodb`:

- timezone-aware timestamp generation and display-name normalization
- boto3 resource setup and table accessors
- user profile synchronization and default-name behavior
- batch user lookup and chunking
- team-member merging, role normalization, and membership lookup
- team lookup helpers
- paginated query and scan helpers
- owned-team and recording-list queries
- recording-duration aggregation for a UTC day, including index fallback handling
- team-name uniqueness checks
- display-name uniqueness checks, including normalization and same-user exceptions
- user resolution by direct identifier or display-name match

### `tests/test_email_integration.py` (1 test)

This suite exercises the `/test-email` route as an integration flow:

- the route reads `SES_TEST_TO`
- the route calls the mock email pipeline
- rendered subject and body content are passed through to the send layer

### `tests/test_email_routes.py` (3 tests)

This suite covers route-level `/test-email` behavior:

- informative message when `SES_TEST_TO` is missing
- successful mocked email send when config is present
- failure reporting when the send operation raises an exception

### `tests/test_lambda.py` (4 tests)

This suite covers Lambda adapter behavior:

- no-op behavior when no API Gateway stage is present
- prefix-header injection when missing
- preservation of an existing prefix header
- handoff from the Lambda entry point to `awsgi.response`

### `tests/test_mock_email.py` (4 tests)

This suite covers mock email generation in `rowlytics_app.services.mock_email`:

- expected send arguments for text and HTML content
- default recipient-name fallback to `"Rower"`
- presence of expected personal/team statistics and app URL content
- propagation of email send errors

### `tests/test_recordings_api.py` (3 tests)

This suite covers recording upload API guardrails:

- presign rejection when the daily two-hour recording limit would be exceeded
- metadata-save rejection when the daily limit would be exceeded
- metadata persistence using the authenticated session user and normalized timestamps

### `tests/test_s3.py` (3 tests)

This suite covers S3 client setup:

- boto3 dependency requirement
- bucket configuration requirement
- successful boto3 client creation

### `tests/test_workout_api.py` (8 tests)

This suite covers workout API validation and scoring helpers:

- rejecting workout durations greater than one hour
- accepting and persisting a one-hour workout
- persisting `armsStraightScore`
- persisting `backStraightScore`
- team workout summary aggregation across available scores
- arms-straightness scoring that ignores finish-phase frames
- high arms-straightness scoring for small bends
- back-straightness scoring for aligned posture and visible arching

## Playwright Accessibility Inventory

### `playwright/tests/a11y.spec.js` (2 tests)

This suite uses `@axe-core/playwright` against the pages listed in `PAGES`:

- `no serious/critical violations on /`
- `no serious/critical violations on /signin`

It filters for `serious` and `critical` WCAG 2 A/AA violations and skips execution unless `A11Y_BASE_URL` is set.

## Manual or Supporting Test Assets

These files are test-related, but they are not part of the automated inventory above:

- `tests/test_documentation/README.txt`
- `tests/test_documentation/aidan_2_8_26_body_detection.txt`
- `tests/test_documentation/example.txt`
- `tests/test_documentation/verification_test_identity`

## Execution Notes

- Pytest entry point:
  `pytest tests`
- Accessibility entry point:
  `npx playwright test`
- Playwright script aliases from `package.json`:
  `npm run a11y:test`, `npm run a11y:test:headed`, `npm run a11y:install`

## Verification Notes

- Pytest counts in this document were derived from the current source files by counting `def test_` declarations under `tests/test_*.py`.
- The Playwright suite count is based on the current `PAGES = ["/", "/signin"]` list in `playwright/tests/a11y.spec.js`, which expands the single test body into 2 concrete test cases.
- I updated this inventory from source and did not execute the automated suites as part of this documentation change.
