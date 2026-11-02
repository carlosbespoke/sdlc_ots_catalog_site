#!/usr/bin/env bash
# Reference solution. Undoes each edit and writes the expected report.
# Proves the task is solvable. Never present in the agent image.
set -euo pipefail
cd /workspace/repo
git apply --whitespace=nowarn /solution/solution.patch
mkdir -p /app
cat > /app/rca.json <<'RCA'
{
  "causes": [
    {
      "file": "checker/check_new_request_non_path_default_parameter.go",
      "function": "NewRequestNonPathDefaultParameterCheck"
    },
    {
      "file": "validate/lint_type_format_mismatch.go",
      "function": "mismatchedFormatOwner"
    },
    {
      "file": "diff/tags_diff.go",
      "function": "TagsDiff.Empty"
    },
    {
      "file": "internal/diff.go",
      "function": "composedDiff"
    },
    {
      "file": "formatters/format_junit.go",
      "function": "JUnitFormatter.RenderChangelog"
    },
    {
      "file": "checker/check_response_discriminator_updated.go",
      "function": "processDiscriminatorDiff"
    },
    {
      "file": "internal/diff.go",
      "function": "runDiff"
    },
    {
      "file": "internal/open_review.go",
      "function": "parseReviewMeta"
    },
    {
      "file": "checker/check_request_parameter_list_of_types_changed.go",
      "function": "RequestParameterListOfTypesChangedCheck"
    },
    {
      "file": "checker/check_request_property_default_value_changed.go",
      "function": "RequestPropertyDefaultValueChangedCheck"
    },
    {
      "file": "diff/modified_subschemas.go",
      "function": "Subschema.String"
    },
    {
      "file": "checker/check_request_parameter_became_nullable.go",
      "function": "RequestParameterBecameNullableCheck"
    },
    {
      "file": "checker/check_api_deprecation.go",
      "function": "formatDeprecationDetailsWithSunset"
    },
    {
      "file": "diff/one_of_wrapping_diff.go",
      "function": "getOneOfWrappingDiff"
    },
    {
      "file": "checker/check_request_property_max_length_set.go",
      "function": "RequestPropertyMaxLengthSetCheck"
    },
    {
      "file": "diff/license_diff.go",
      "function": "LicenseDiff.Empty"
    },
    {
      "file": "checker/check_response_property_max_length_unset.go",
      "function": "ResponsePropertyMaxLengthUnsetCheck"
    },
    {
      "file": "checker/check_request_parameters_min_set.go",
      "function": "RequestParameterMinSetCheck"
    },
    {
      "file": "checker/check_api_deprecation.go",
      "function": "APIDeprecationCheck"
    },
    {
      "file": "internal/checks_changelog.go",
      "function": "outputChangelogRules"
    },
    {
      "file": "diff/license_diff.go",
      "function": "getLicenseDiff"
    },
    {
      "file": "checker/component_change.go",
      "function": "ComponentChange.MatchIgnore"
    },
    {
      "file": "checker/check_request_property_x_extensible_enum_value_removed.go",
      "function": "RequestPropertyXExtensibleEnumValueRemovedCheck"
    },
    {
      "file": "diff/license_diff.go",
      "function": "getLicenseDiffInternal"
    },
    {
      "file": "formatters/format_json.go",
      "function": "emptyDocFor"
    },
    {
      "file": "validate/lint_type_format_mismatch.go",
      "function": "withoutNullType"
    }
  ]
}
RCA
