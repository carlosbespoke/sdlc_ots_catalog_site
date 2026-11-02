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
      "file": "analysis/stratification.go",
      "function": "Stratify"
    },
    {
      "file": "unionfind/unifytypeexpr.go",
      "function": "UnifyTypeExpr"
    },
    {
      "file": "json2struct/json2struct.go",
      "function": "ConvertValue"
    },
    {
      "file": "ast/decl.go",
      "function": "Decl.FunDeps"
    },
    {
      "file": "provenance/facts.go",
      "function": "EmitFacts"
    },
    {
      "file": "functional/functional.go",
      "function": "EvalApplyFn"
    },
    {
      "file": "rewrite/rewrite.go",
      "function": "freshNameGenerator"
    },
    {
      "file": "builtin/builtin.go",
      "function": "Decide"
    },
    {
      "file": "factstore/temporal.go",
      "function": "TemporalStore.Add"
    },
    {
      "file": "parse/parse.go",
      "function": "Parser.VisitMember"
    },
    {
      "file": "packages/packages.go",
      "function": "findPackage"
    },
    {
      "file": "analysis/rectify.go",
      "function": "RectifyAtom"
    },
    {
      "file": "symbols/nametrie.go",
      "function": "NameTrie.Collect"
    },
    {
      "file": "ast/temporal.go",
      "function": "Interval.Overlaps"
    },
    {
      "file": "provenance/provenance.go",
      "function": "Explain"
    },
    {
      "file": "rewrite/rewrite.go",
      "function": "isSingleAtomPremise"
    },
    {
      "file": "engine/premise.go",
      "function": "premiseNegAtom"
    },
    {
      "file": "builtin/builtin.go",
      "function": "match"
    },
    {
      "file": "factstore/temporal.go",
      "function": "coalesceIntervals"
    },
    {
      "file": "analysis/varlist.go",
      "function": "VarList.Contains"
    },
    {
      "file": "symbols/decldesugar.go",
      "function": "typeBoundForPredicate"
    },
    {
      "file": "provenance/recorder.go",
      "function": "builder.buildRule"
    },
    {
      "file": "engine/premise.go",
      "function": "premiseIneq"
    },
    {
      "file": "builtin/temporal.go",
      "function": "intervalBefore"
    },
    {
      "file": "factstore/factstore.go",
      "function": "MultiIndexedArrayInMemoryStore.GetFacts"
    },
    {
      "file": "symbols/typeexprs.go",
      "function": "StructTypeField"
    },
    {
      "file": "analysis/boundscheck.go",
      "function": "boundOfArg"
    },
    {
      "file": "ast/decl.go",
      "function": "Decl.MergePredicate"
    },
    {
      "file": "ast/temporal.go",
      "function": "Date"
    },
    {
      "file": "builtin/temporal.go",
      "function": "intervalDuring"
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
