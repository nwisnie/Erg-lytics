# Rowlytics Test Inventory

Last updated: 2026-03-15

This document inventories the tests currently present in the repository. Current automated tests and test documentation are located under `tests/` and `playwright/tests/`.

## Current Automated Test Suites

| Suite | Framework | Test count | Focus |
| --- | --- | ---: | --- |
| `tests/test_alignment.py` | `pytest` | 23 | Practice-stroke assembly, progression-step generation, progression matching, and ideal-model coordinate selection |
| `tests/test_app.py` | `pytest` | 6 | Flask app creation and basic route rendering |
| `tests/test_auth.py` | `pytest` | 20 | Cognito helpers, token parsing, login URL generation, token exchange, user deletion, session context |
| `tests/test_dynamodb.py` | `pytest` | 37 | DynamoDB resource/table access, profile sync, batch lookup, membership/team queries, pagination helpers |
| `tests/test_lambda.py` | `pytest` | 4 | Lambda adapter behavior and stage prefix header injection |
| `tests/test_s3.py` | `pytest` | 3 | S3 client initialization and required configuration checks |
| `tests/test_email_routes.py` | `pytest` | 3 | `/test-email` route behavior and SES test-email handling |
| `playwright/tests/a11y.spec.js` | `Playwright + axe-core` | 2 | Accessibility baseline checks for `/` and `/signin` |

Current automated inventory total: 103 tests

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

### `tests/test_dynamodb.py` (36 tests)

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
  `test_get_team_returns_item`, `test_get_team_returns_none_when_not_found`, `test_get_team_propagates_errors`
- Pagination helpers:
  `test_query_all_handles_multiple_pages`, `test_scan_all_handles_multiple_pages`
- Membership and ownership listing:
  `test_list_team_memberships_uses_query_all`, `test_list_team_memberships_falls_back_to_scan_on_validation_error`, `test_list_team_members_by_team_delegates_to_query_all`, `test_list_owned_teams_returns_empty_when_attr_missing`, `test_list_owned_teams_calls_scan_all`, `test_list_recordings_delegates_to_query_all`, `test_query_all_returns_empty_list`
- Team name existence checks:
  `test_team_name_exists_returns_false_for_empty_name`, `test_team_name_exists_raises_when_attr_missing`, `test_team_name_exists_true_when_query_returns_item`, `test_team_name_exists_uses_scan_when_query_empty`, `test_team_name_exists_fallback_on_allowed_client_error`, `test_team_name_exists_reraises_unexpected_client_error`

### `tests/test_lambda.py` (4 tests)

- `test_inject_stage_prefix_no_stage_returns_event_unchanged`
- `test_inject_stage_prefix_sets_header_when_missing`
- `test_inject_stage_prefix_preserves_existing_prefix_header`
- `test_lambda_handler_calls_awsgi_response`

These cover API Gateway stage-prefix header behavior and the Lambda-to-Flask adapter handoff.

### `tests/test_s3.py` (3 tests)

- `test_get_s3_client_requires_boto3`
- `test_get_s3_client_requires_bucket`
- `test_get_s3_client_returns_boto_client`

These validate S3 client creation prerequisites and the normal boto3 client path.

### `tests/test_email_routes.py` (3 tests)

- `test_test_email_route_returns_message_when_env_missing`
  Confirms the `/test-email` endpoint returns an informative message when `SES_TEST_TO` is not configured.

- `test_test_email_route_sends_mock_email_when_env_present`
  Uses a mocked email sender to verify the route attempts to send an email when `SES_TEST_TO` is configured.

- `test_test_email_route_returns_failure_message_when_send_fails`
  Verifies the route correctly reports an error when the mocked email send operation raises an exception.

## Playwright Accessibility Inventory

### `playwright/tests/a11y.spec.js` (2 tests)

- `no serious/critical violations on /`
- `no serious/critical violations on /signin`

This suite uses `@axe-core/playwright` and filters for `serious` and `critical` WCAG 2 A/AA violations. The suite is skipped unless `A11Y_BASE_URL` is set.

## Manual or Supporting Test Assets

These files are test-related, but they are not part of the automated inventory above:

`tests/test_documentation/aidan_2_8_26_body_detection.txt`
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

- Playwright discovery was confirmed locally with `npx playwright test --list`, which reported 2 tests.
- Pytest collection could not be executed in the current environment because local Python dependencies are missing, including `flask` and `botocore`.
- The pytest counts in this document are therefore based on the currently committed test source files and discovered `def test_*` functions.
