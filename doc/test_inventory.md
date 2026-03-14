# Rowlytics Test Inventory

Last updated: 2026-03-14

This document inventories the tests currently present in the repository. Current automated tests and test documentation are located under `tests/` and `playwright/tests/`.

## Current Automated Test Suites

| Suite | Framework | Test count | Focus |
| --- | --- | ---: | --- |
| `tests/test_app.py` | `pytest` | 3 | Flask app creation and basic route rendering |
| `tests/test_auth.py` | `pytest` | 13 | Cognito helpers, token parsing, login URL generation, token exchange, user deletion, session context |
| `tests/test_dynamodb.py` | `pytest` | 36 | DynamoDB resource/table access, profile sync, batch lookup, membership/team queries, pagination helpers |
| `tests/test_lambda.py` | `pytest` | 4 | Lambda adapter behavior and stage prefix header injection |
| `tests/test_s3.py` | `pytest` | 3 | S3 client initialization and required configuration checks |
| `tests/test_email_routes.py` | `pytest` | 3 | `/test-email` route behavior and SES test-email handling |
| `playwright/tests/a11y.spec.js` | `Playwright + axe-core` | 2 | Accessibility baseline checks for `/` and `/signin` |

Current automated inventory total: 64 tests

## Pytest Inventory

### `tests/conftest.py`

Shared pytest bootstrap only. It inserts the project root into `sys.path` so tests can import the app package when run directly.

### `tests/test_app.py` (3 tests)

- `test_create_app_returns_flask_instance`
  Confirms `create_app()` returns a Flask app and exposes an expected `ROWLYTICS_ENV` value.
- `test_landing_page_renders_expected_copy`
  Smoke test for `GET /`, including expected landing-page copy.
- `test_template_detail_route`
  Confirms `GET /templates/capture-workout` returns `200` and renders expected content.

### `tests/test_auth.py` (13 tests)

- Token parsing:
  `test_decode_token_payload_returns_dict`, `test_decode_token_payload_handles_errors`
- Cognito login URL generation:
  `test_build_cognito_login_url_missing_config_returns_none`, `test_build_cognito_login_url_builds_expected_url`
- OAuth token exchange:
  `test_exchange_code_for_tokens_requires_config`, `test_exchange_code_for_tokens_posts_and_parses_response`
- Cognito client creation:
  `test_get_cognito_client_requires_boto3`, `test_get_cognito_client_returns_client`
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
  `test_list_team_memberships_uses_query_all`, `test_list_team_memberships_falls_back_to_scan_on_validation_error`, `test_list_team_members_by_team_delegates_to_query_all`, `test_list_owned_teams_returns_empty_when_attr_missing`, `test_list_owned_teams_calls_scan_all`, `test_list_recordings_delegates_to_query_all`
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
