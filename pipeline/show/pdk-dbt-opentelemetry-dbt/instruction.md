Since our telemetry exporters changed, the resource dimension in /app is wrong.

The same resource's attributes can arrive with the keys in another order, spaces after colons and commas, or an extra pair of double quotes around them. Some observed_timestamp, end_timestamp and start_timestamp values are in microseconds or nanoseconds. Sightings fall between the years 2000 and 2100, so drop the extra digits to get whole milliseconds.

dim_otel_resources needs one row per resource, meaning one set of attribute keys and values, and missing or empty attributes in any form are not a resource. first_seen_at_ms and last_seen_at_ms are its earliest and latest sighting, from the row's observed_timestamp, end_timestamp or start_timestamp, or a gauge or sum point's own timestamp in UTC when start_timestamp is 0. A null value there is no sighting. A repeated build, a build after a later batch with older records or replays, and a full refresh must match a fresh build.

Fact rows with a resource must join it on resource_id so service_name is filled, and their observed_at, ended_at and started_at must be right, with started_at null when start_timestamp is 0. rpt_otel_service_inventory counts each resource once per service grouping in instance_count, with first_seen_at and last_seen_at from those bounds.

I run dbt seed and then dbt build in /app/integration_tests. Everything else keeps its output, and the project's unit and data tests must pass unchanged. The project stays SQL: only SQL models, macros and YAML, with no Python models. dbt and DuckDB are installed, and there's no network.
