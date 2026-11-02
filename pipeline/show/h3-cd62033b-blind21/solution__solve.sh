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
      "file": "src/h3lib/lib/linkedGeo.c",
      "function": "linkedGeoPolygonToGeoMultiPolygon"
    },
    {
      "file": "src/h3lib/lib/polygon.c",
      "function": "lineCrossesLine"
    },
    {
      "file": "src/h3lib/lib/polyfill.c",
      "function": "iterStepPolygonCompact"
    },
    {
      "file": "src/h3lib/lib/h3Index.c",
      "function": "cellToChildPos"
    },
    {
      "file": "src/h3lib/lib/vertex.c",
      "function": "cellToVertexes"
    },
    {
      "file": "src/h3lib/lib/localij.c",
      "function": "localIjkToCell"
    },
    {
      "file": "src/h3lib/lib/polygon.c",
      "function": "validatePolygonFlags"
    },
    {
      "file": "src/h3lib/lib/latLng.c",
      "function": "edgeLengthM"
    },
    {
      "file": "src/h3lib/lib/localij.c",
      "function": "cellToLocalIjk"
    },
    {
      "file": "src/h3lib/lib/area.c",
      "function": "cellAreaKm2"
    },
    {
      "file": "src/h3lib/lib/area.c",
      "function": "cagnoli"
    },
    {
      "file": "src/h3lib/lib/directedEdge.c",
      "function": "areNeighborCells"
    },
    {
      "file": "src/h3lib/lib/vertex.c",
      "function": "vertexRotations"
    },
    {
      "file": "src/h3lib/lib/polyfill.c",
      "function": "cellToBBox"
    },
    {
      "file": "src/h3lib/lib/baseCells.c",
      "function": "_isBaseCellPolarPentagon"
    },
    {
      "file": "src/h3lib/lib/polyfill.c",
      "function": "maxPolygonToCellsSizeExperimental"
    },
    {
      "file": "src/h3lib/lib/vertex.c",
      "function": "cellToVertex"
    }
  ]
}
RCA
