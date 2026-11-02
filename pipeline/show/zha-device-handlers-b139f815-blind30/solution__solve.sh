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
      "file": "zhaquirks/sinope/__init__.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/tuya/ts0601_electric_heating.py",
      "function": "map_attribute"
    },
    {
      "file": "zhaquirks/schneiderelectric/outlet.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/candeo/__init__.py",
      "function": "lux_calibration"
    },
    {
      "file": "zhaquirks/linkind/motion.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/ubisys/cover_j1.py",
      "function": "_read_calibration_attributes"
    },
    {
      "file": "zhaquirks/tuya/builder/__init__.py",
      "function": "tuya_cover"
    },
    {
      "file": "zhaquirks/sonoff/zbm5.py",
      "function": "write_attributes"
    },
    {
      "file": "zhaquirks/konke/__init__.py",
      "function": "handle_cluster_general_request"
    },
    {
      "file": "zhaquirks/xiaomi/aqara/switch_acn047.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/thirdreality/night_light.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/builder/builder.py",
      "function": "__call__"
    },
    {
      "file": "zhaquirks/device.py",
      "function": "add_endpoint"
    },
    {
      "file": "zhaquirks/bituo/spm01.py",
      "function": "is_attribute_unsupported"
    },
    {
      "file": "zhaquirks/legrand/cable_outlet.py",
      "function": "write_attributes"
    },
    {
      "file": "zhaquirks/smartwings/wm25lz.py",
      "function": "command"
    },
    {
      "file": "zhaquirks/tuya/tuya_co.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/ubisys/cover_j1.py",
      "function": "_wait_until_stopped"
    },
    {
      "file": "zhaquirks/tuya/builder/__init__.py",
      "function": "tuya_battery"
    },
    {
      "file": "zhaquirks/xiaomi/aqara/roller_curtain_e1.py",
      "function": "command"
    },
    {
      "file": "zhaquirks/tuya/ts0601_electric_heating.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/tuya/__init__.py",
      "function": "write_attributes"
    },
    {
      "file": "zhaquirks/tuya/tuya_smoke.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/clusters.py",
      "function": "get"
    },
    {
      "file": "zhaquirks/xiaomi/aqara/thermostat_agl001.py",
      "function": "_write_temp_to_buf"
    },
    {
      "file": "zhaquirks/tuya/tuya_co.py",
      "function": "tuya_air_quality_temperature_converter"
    },
    {
      "file": "zhaquirks/candeo/__init__.py",
      "function": "_update_attribute"
    },
    {
      "file": "zhaquirks/xiaomi/__init__.py",
      "function": "_iter_parse_attr_report"
    },
    {
      "file": "zhaquirks/linxura/button.py",
      "function": "_handle_attribute_event"
    },
    {
      "file": "zhaquirks/philips/__init__.py",
      "function": "press"
    }
  ]
}
RCA
mkdir -p "$(dirname /app/RESEARCH_AND_PLANNING.md)"
cat > /app/RESEARCH_AND_PLANNING.md <<'PLAN'
# Research and plan

## What I investigated
I read the reported misbehaviours and traced each one to the function whose output
changed, comparing the broken areas against neighbouring code that still works to localise
the edits rather than guessing from names.

## Constraints that shape the change
Each defect is a single-line edit inside one function. The fix must restore the original
behaviour at that site without touching unrelated code, and must be reachable from the same
call paths the reports describe.

## How I will carry it out
Restore each identified site to the behaviour the reports expect, record every edited
function in /app/rca.json, then verify by re-exercising the affected behaviours and
confirming the previously-wrong outputs are correct again while the working neighbours stay
working.
PLAN
