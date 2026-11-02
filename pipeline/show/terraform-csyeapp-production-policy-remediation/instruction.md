# CSYE production: pass the policy pack without disruption

CI is red on the CSYE production stack in `/workspace/infra`: its plan against the recorded state is clean, but the platform policy pack in `policies/` fails on it. The code also ignores the input and owner handling `variables.tf` describes.

## What we need

- `scripts/ci-plan.sh` passes; `policies/README.md` explains each rule.
- Every resource in `terraform.tfstate` stays at its address, at most updated in place, without `moved`, `removed` or `import` blocks.
- In-place updates touch only these arguments: `aws_cloudwatch_log_group` `retention_in_days`; `aws_cloudwatch_metric_alarm` `actions_enabled`, `alarm_actions`, `insufficient_data_actions`, `ok_actions`; `aws_db_instance` `apply_immediately`, `copy_tags_to_snapshot`, `enabled_cloudwatch_logs_exports`, `iam_database_authentication_enabled`, `iops`, `storage_throughput`, `storage_type`; `aws_db_parameter_group` `tags`; `aws_dynamodb_table` `billing_mode`, `read_capacity`, `write_capacity`; `aws_flow_log` `max_aggregation_interval`, `traffic_type`; `aws_iam_policy` and `aws_iam_role_policy` `policy`; `aws_iam_role` `assume_role_policy`, `inline_policy`, `max_session_duration`, `permissions_boundary`; `aws_kms_alias` `target_key_id`; `aws_kms_key` `bypass_policy_lockout_safety_check`, `policy`; `aws_lambda_function` `logging_config`, `tracing_config`; `aws_launch_template` `block_device_mappings`, `default_version`, `instance_type`, `monitoring`, `tag_specifications`, `update_default_version` (its `latest_version` follows); `aws_lb` `access_logs`; `aws_lb_listener` `default_action`; `aws_s3_bucket_lifecycle_configuration` `rule`. Tags may also change anywhere else, but only in the keys `CostCenter`, `DataClassification`, `Environment` and `Owner`.
- New resources only of types `aws_cloudwatch_log_group`, `aws_cloudwatch_metric_alarm`, `aws_flow_log`, `aws_kms_alias`, `aws_s3_bucket_lifecycle_configuration`, `aws_s3_bucket_logging` and `aws_s3_bucket_policy`.
- Network, application and channel log groups use the requested `log_retention_days` (a channel's own, else the root one), raised to 120 days when lower.
- An `app_instance_type` in an approved family is used as is; `t2.<size>` becomes `t3.<size>`.
- Every `CostCenter` tag is the root `tags` value upper-cased.
- Each channel's Lambda function and each bucket are tagged `Owner` with their entry's `owner`.
- No override or `.tf.json` files, provisioners, `ignore_changes`/`replace_triggered_by`, `backend`/`cloud` blocks, `provider` blocks outside `providers.tf`, or `external`/`http`/`terraform_remote_state` data sources.
- All of this holds, with no other edit, for a `-var-file` that sets `log_retention_days`, `app_instance_type` or `tags`, or adds, removes or edits `channels` or `buckets` keys (added keys count as already deployed by today's code). What today's code itself plans for such an edit, like destroying a removed key's resources, is fine too.

## Keep working

- Root variable declarations (descriptions aside) and values
- `providers.tf`, `versions.tf`, `scripts/ci-plan.sh` and `policies/`, byte for byte; no `conftest.toml`
- Bucket size alarm thresholds at `alarm_gib`, in bytes

## Setup

No AWS access: Terraform 1.16.4 and AWS provider 5.100.0 run offline, so nothing may call AWS at plan time. Leave `terraform.tfstate` (the recorded production state) and `.terraform.lock.hcl` as is. `scripts/ci-plan.sh` is what CI runs; extra arguments like `-var-file` go to the plan.
