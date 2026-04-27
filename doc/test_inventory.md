# Rowlytics Test Inventory

Last updated: 2026-04-27

This document inventories the tests currently present in the repository. Automated tests live under `tests/` and `playwright/tests/`. Manual test artifacts live under `tests/test_documentation/`.

## Current Automated Test Suites

| Suite | Framework | Test count | Focus |
| --- | --- | ---: | --- |
| `tests/test_alignment.py` | `pytest` | 23 | Practice-stroke assembly, progression-step generation, progression matching, and ideal-model coordinate selection |
| `tests/test_capture_workout_save.py` | `pytest` | 3 | Capture-workout save gating, workout-analysis snapshot preservation, and threshold rejection behavior |
| `tests/test_angles.py` | `pytest` | 2 | Normalized joint-angle calculation and zero-length segment validation |
| `tests/test_app.py` | `pytest` | 8 | Flask app creation, core route rendering, auth URL integration, and static asset availability |
| `tests/test_auth.py` | `pytest` | 20 | Cognito token parsing, login URL generation, token exchange, token expiry, user deletion, and session helpers |
| `tests/test_deviation.py` | `pytest` | 26 | Skeletal deviation math helpers, limb/torso deviation scoring, midpoint handling, and full pose comparison |
| `tests/test_display_name_flow.py` | `pytest` | 6 | Display-name onboarding, auth callback redirects, gated navigation, and account-name updates |
| `tests/test_dynamodb.py` | `pytest` | 62 | DynamoDB resource/table access, profile sync, memberships, recordings/workouts date queries, name uniqueness, and identifier resolution |
| `tests/test_email_integration.py` | `pytest` | 1 | End-to-end `/test-email` route integration with the mock email pipeline |
| `tests/test_email_routes.py` | `pytest` | 3 | `/test-email` route behavior for missing config, success, and failure paths |
| `tests/test_lambda.py` | `pytest` | 4 | Lambda adapter behavior and API Gateway stage-prefix header injection |
| `tests/test_mock_email.py` | `pytest` | 4 | Mock email composition, default-name fallback, content generation, and send-error propagation |
| `tests/test_recordings_api.py` | `pytest` | 6 | Recording upload guardrails, daily duration limits, metadata normalization, and date-range filtering |
| `tests/test_s3.py` | `pytest` | 3 | S3 client initialization and required configuration checks |
| `tests/test_team_stats_api.py` | `pytest` | 3 | Weekly team statistics route auth checks, user/team aggregate responses, and empty team-state handling |
| `tests/test_workout_api.py` | `pytest` | 12 | Workout validation, score persistence, date-range filtering, team summary aggregation, and posture scoring helpers |
| `tests/test_workout_save_integration.py` | `pytest` | 1 | Integration coverage for the workout save API route, verifying workout analysis fields are persisted through the real route/save flow while mocking only the external DynamoDB resource layer |
| `playwright/tests/a11y.spec.js` | `Playwright + axe-core` | 2 | Accessibility baseline checks for `/` and `/signin` |

Current automated inventory total: 189 tests

- Pytest total: 187 tests
- Playwright total: 2 tests

## Pytest Inventory

### `tests/conftest.py`

Shared pytest bootstrap only. It inserts the project root into `sys.path` so tests can import the app package when run directly.

### `tests/test_alignment.py` (23 tests)

- `test_init_sets_default_values`
  Confirms a new `PracticeStrokeAssembler` starts with an empty coordinate list and `finished == False`.
- `test_assemble_practice_strokes_adds_valid_coordinate`
  Confirms valid coordinate dictionaries are appended in normalized form.
- `test_assemble_practice_strokes_returns_coordinates_when_finished`
  Confirms passing `"finished"` marks the assembler complete and returns the accumulated coordinates.
- `test_assemble_practice_strokes_raises_error_for_non_dict_input`
  Confirms non-dictionary practice-stroke input is rejected.
- `test_assemble_practice_strokes_raises_error_for_missing_keys`
  Confirms incomplete coordinate dictionaries are rejected.
- `test_assemble_progression_steps_raises_error_for_invalid_coordinates_type`
  Confirms `assemble_progression_steps()` rejects non-list coordinate input.
- `test_assemble_progression_steps_raises_error_for_too_few_coordinates`
  Confirms at least two coordinates are required to build progression steps.
- `test_assemble_progression_steps_raises_error_for_non_numeric_interval`
  Confirms `progression_interval` must be numeric.
- `test_assemble_progression_steps_raises_error_for_interval_too_small`
  Confirms intervals below the accepted range are rejected.
- `test_assemble_progression_steps_raises_error_for_interval_too_large`
  Confirms intervals above the accepted range are rejected.
- `test_assemble_progression_steps_returns_single_step_when_all_x_are_same`
  Confirms a degenerate all-same-`x` trace produces a single progression step.
- `test_assemble_progression_steps_generates_expected_steps`
  Confirms normalized progression steps are generated at the expected intervals.
- `test_assemble_progression_steps_forces_final_progression_step_to_one`
  Confirms the final generated step is normalized to `1.0`.
- `test_match_progression_interval_raises_error_for_empty_progression_intervals`
  Confirms progression matching requires a non-empty progression-interval list.
- `test_match_progression_interval_raises_error_for_empty_coordinate_list`
  Confirms progression matching requires a non-empty current coordinate list.
- `test_match_progression_interval_raises_error_when_name_not_found`
  Confirms progression matching fails when the target body part is absent.
- `test_match_progression_interval_returns_closest_progression_step`
  Confirms the closest stored progression step is selected for the matching body part.
- `test_get_ideal_coordinate_set_raises_error_for_non_dict_progression_step`
  Confirms `get_ideal_coordinate_set()` requires a dictionary input for the current progression step.
- `test_get_ideal_coordinate_set_raises_error_when_progression_step_missing`
  Confirms the current progression step must include a `progression_step` value.
- `test_get_ideal_coordinate_set_raises_error_when_time_missing`
  Confirms the current progression step must include a `time` value.
- `test_get_ideal_coordinate_set_raises_error_for_empty_ideal_model`
  Confirms the ideal-model input must be a non-empty list.
- `test_get_ideal_coordinate_set_raises_error_when_no_progression_steps_exist`
  Confirms the ideal-model input must contain usable `progression_step` values.
- `test_get_ideal_coordinate_set_returns_unique_bodyparts_for_closest_step`
  Confirms the closest ideal progression step is selected and duplicate body-part names are collapsed to unique entries.

### `tests/test_app.py` (3 tests)

- `test_create_app_returns_flask_instance`
  Confirms `create_app()` returns a Flask app and exposes an expected `ROWLYTICS_ENV` value.
- `test_landing_page_renders_expected_copy`
  Smoke test for `GET /`, including expected landing-page copy.
- `test_template_detail_route`
  Confirms `GET /templates/capture-workout` returns `200` and renders expected content.
- `test_unknown_route`
  Confirms running a `.get()` request with an unknown page returns `404`
- `test_landing_page_post_not_allowed`
  This runs a `.post()` request on the root page and confirms it cannot be written to
- `test_cognito_login_url_integration`
  This is an integration test between the cognito login features and the flask app

### `tests/test_auth.py` (13 tests)

- Token parsing:
  `test_decode_token_payload_returns_dict`, `test_decode_token_payload_handles_errors`, `test_decode_token_payload_empty_token`, `test_decode_token_payload_invalid_json`
- Cognito login URL generation:
  `test_build_cognito_login_url_missing_config_returns_none`, `test_build_cognito_login_url_builds_expected_url`,  `test_build_cognito_login_url_returns_none_when_domain_missing`
- OAuth token exchange:
  `test_exchange_code_for_tokens_requires_config`, `test_exchange_code_for_tokens_posts_and_parses_response`, `test_token_expired`, `test_exchange_code_for_tokens_sends_form_encoded_request`, `test_exchange_code_for_tokens_integration`
- Cognito client creation:
  `test_get_cognito_client_requires_boto3`, `test_get_cognito_client_returns_client`, `test_get_current_user`
- Cognito user deletion paths:
  `test_delete_cognito_user_uses_access_token`, `test_delete_cognito_user_fallbacks_to_admin_delete`, `test_delete_cognito_user_requires_pool_or_username`, `test_delete_cognito_user_raises_with_last_error`
- Session helper:
  `test_user_context_reads_from_flask_session`

### `tests/test_capture_workout_save.py` (3 tests)

- `test_workout_analysis_snapshot_values_are_preserved`
  Confirms workout-save payloads preserve passed analysis values such as summary, workout score, alignment details, stroke count, cadence, range of motion, arm/back straightness, and dominant side.

- `test_workout_analysis_snapshot_handles_missing_analysis`
  Confirms workout-save payloads fall back safely when no workout analysis is available, including use of the default summary and `None` values for optional metrics.

- `test_clip_threshold_rejection_behavior`
  Confirms capture-workout save gating rejects clips when the score is missing or above the threshold and allows saves when the score is within the accepted range.

### `tests/test_dynamodb.py` (62 tests)

- Utility and client/resource setup:
  `test_now_iso_returns_timezone_aware_isoformat`, `test_get_resource_requires_boto3`, `test_get_resource_uses_boto3_resource`
- Table accessors:
  `test_get_users_table_returns_table`, `test_get_team_members_table_returns_table`, `test_get_teams_table_returns_table`, `test_get_recordings_table_raises_when_missing_env`, `test_get_ddb_tables_returns_user_and_member_tables`
- User profile sync:
  `test_sync_user_profile_returns_name_when_no_user_id`, `test_sync_user_profile_updates_with_email_and_derived_name`, `test_sync_user_profile_returns_original_name_on_update_error`
- Batch user lookup:
  `test_batch_get_users_returns_empty_dict_when_no_ids`, `test_batch_get_users_handles_chunking`, `test_batch_get_users_propagates_exception`
- Team member assembly and membership lookup:
  `test_fetch_team_members_merges_users_and_normalizes_roles`, `test_get_team_membership_returns_first_item`, `test_get_team_membership_returns_none_when_missing`, `test_get_team_membership_fallbacks_to_scan_on_validation_error`, `test_get_team_membership_reraises_unexpected_client_error`
- Team lookup:
  `test_get_team_returns_item`, `test_get_team_returns_none_when_not_found`, `test_get_team_propagates_errors`, `test_fetch_team_members_page_merges_users_and_normalizes_roles`
- Pagination helpers:
  `test_query_all_handles_multiple_pages`, `test_scan_all_handles_multiple_pages`,
  `test_query_page_returns_items_and_last_evaluated_key`,
  `test_query_page_with_exclusive_start_key`,
  `test_query_page_handles_missing_last_evaluated_key`,
  `test_query_page_handles_no_items`,
  `test_list_recordings_page_calls_query_page`,
  `test_list_workouts_page_calls_query_page`
- Membership and ownership listing:
  `test_list_team_memberships_uses_query_all`, `test_list_team_memberships_falls_back_to_scan_on_validation_error`, `test_list_team_members_by_team_delegates_to_query_all`, `test_list_owned_teams_returns_empty_when_attr_missing`, `test_list_owned_teams_calls_scan_all`, `test_list_recordings_delegates_to_query_all`, `test_query_all_returns_empty_list`
- Team name existence checks:
  `test_team_name_exists_returns_false_for_empty_name`, `test_team_name_exists_raises_when_attr_missing`, `test_team_name_exists_true_when_query_returns_item`, `test_team_name_exists_uses_scan_when_query_empty`, `test_team_name_exists_fallback_on_allowed_client_error`, `test_team_name_exists_reraises_unexpected_client_error`
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

### `tests/test_dynamodb.py` (52 tests)

This suite covers DynamoDB-related helpers in `rowlytics_app.services.dynamodb`:

- timezone-aware timestamp generation and display-name normalization
- boto3 resource setup and table accessors
- user profile synchronization and default-name behavior
- batch user lookup and chunking
- team-member merging, role normalization, and membership lookup
- team lookup helpers
- paginated query and scan helpers
- owned-team and recording-list queries
- paginated recording and workout date-range queries
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

### `tests/test_recordings_api.py` (6 tests)

This suite covers recording upload API guardrails:

- presign rejection when the daily two-hour recording limit would be exceeded
- metadata-save rejection when the daily limit would be exceeded
- metadata persistence using the authenticated session user and normalized timestamps
- created-at range query forwarding for recording list filtering
- rejection of incomplete created-at range query parameters

### `tests/test_s3.py` (3 tests)

This suite covers S3 client setup:

- boto3 dependency requirement
- bucket configuration requirement
- successful boto3 client creation

### `tests/test_team_stats_api.py` (3 tests)

This suite covers team statistics API behavior:

- weekly team statistics aggregation across team members
- empty team-stat responses when the current user is not on a team
- weekly score point filtering and ordering for team chart data

### `tests/test_workout_api.py` (12 tests)

This suite covers workout API validation and scoring helpers:

- rejecting workout durations greater than one hour
- accepting and persisting a one-hour workout
- persisting `armsStraightScore`
- persisting `backStraightScore`
- completed-at range query forwarding for workout summary filtering
- rejection of incomplete completed-at range query parameters
- team workout summary aggregation across available scores
- arms-straightness scoring that ignores finish-phase frames
- high arms-straightness scoring for small bends
- back-straightness scoring for aligned posture and visible arching

### `tests/test_workout_save_integration.py` (1 test)

This suite covers the workout save API flow as an integration test:

- posts workout analysis data through the real Flask workout save route
- verifies the route returns a successful response
- confirms saved workout data preserves summary, score, alignment details, stroke count, cadence, range of motion, arm/back scores, and dominant side
- mocks only the external DynamoDB resource layer so the test does not require live AWS access

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
