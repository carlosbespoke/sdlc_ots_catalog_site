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
      "file": "internal/bitmap/bitmap.go",
      "function": "Bitmap.Not"
    },
    {
      "file": "internal/api/apiservice/rebuild_lro.go",
      "function": "toAttemptKey"
    },
    {
      "file": "pkg/stabilize/custom.go",
      "function": "ExcludePath.Stabilizer"
    },
    {
      "file": "internal/gitcache/client.go",
      "function": "Client.GetLinkWithRef"
    },
    {
      "file": "internal/netclassify/classify.go",
      "function": "classifyNPMURL"
    },
    {
      "file": "internal/netclassify/classify.go",
      "function": "classifyPyPIFile"
    },
    {
      "file": "internal/bitmap/bitmap.go",
      "function": "Bitmap.Get"
    },
    {
      "file": "pkg/archive/tar.go",
      "function": "ExtractTar"
    },
    {
      "file": "pkg/registry/rubygems/rubygems.go",
      "function": "HTTPRegistry.Version"
    },
    {
      "file": "pkg/build/local/run_args.go",
      "function": "composeContainerArgs"
    },
    {
      "file": "pkg/build/local/run_args.go",
      "function": "ComposeDockerExecArgs"
    },
    {
      "file": "internal/netclassify/classify.go",
      "function": "classifyAlpineURL"
    },
    {
      "file": "pkg/registry/cratesio/cratesio.go",
      "function": "HTTPRegistry.Crate"
    },
    {
      "file": "pkg/stabilize/custom.go",
      "function": "CreateCustomStabilizers"
    },
    {
      "file": "internal/gitcache/server.go",
      "function": "Server.HandleGet"
    },
    {
      "file": "internal/netclassify/classify.go",
      "function": "classifyOCIRegistryURL"
    },
    {
      "file": "internal/gitcache/client.go",
      "function": "Client.Clone"
    },
    {
      "file": "internal/netclassify/classify.go",
      "function": "classifyMavenURL"
    }
  ]
}
RCA
