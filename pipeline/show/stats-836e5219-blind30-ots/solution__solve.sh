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
      "file": "mode.go",
      "function": "Mode"
    },
    {
      "file": "sample.go",
      "function": "Sample"
    },
    {
      "file": "ztest.go",
      "function": "ZTest"
    },
    {
      "file": "percentile_of_score.go",
      "function": "PercentileOfScore"
    },
    {
      "file": "mean.go",
      "function": "HarmonicMean"
    },
    {
      "file": "trimmed_mean.go",
      "function": "TrimmedMean"
    },
    {
      "file": "geometric_distribution.go",
      "function": "VarGeom"
    },
    {
      "file": "interp.go",
      "function": "Interp"
    },
    {
      "file": "sigmoid.go",
      "function": "Sigmoid"
    },
    {
      "file": "coefficient_of_variation.go",
      "function": "CoefficientOfVariation"
    },
    {
      "file": "product.go",
      "function": "Product"
    },
    {
      "file": "zscore.go",
      "function": "ZScore"
    },
    {
      "file": "distances.go",
      "function": "MinkowskiDistance"
    },
    {
      "file": "regression.go",
      "function": "LinearRegression"
    },
    {
      "file": "ttest.go",
      "function": "TTest"
    },
    {
      "file": "norm.go",
      "function": "normLogTail"
    },
    {
      "file": "quartile.go",
      "function": "Trimean"
    },
    {
      "file": "percentile.go",
      "function": "PercentileNearestRank"
    },
    {
      "file": "softmax.go",
      "function": "SoftMax"
    },
    {
      "file": "load.go",
      "function": "LoadRawData"
    },
    {
      "file": "winsorize.go",
      "function": "Winsorize"
    },
    {
      "file": "rolling.go",
      "function": "MovingAverage"
    },
    {
      "file": "weighted_mean.go",
      "function": "WeightedMean"
    },
    {
      "file": "entropy.go",
      "function": "Entropy"
    },
    {
      "file": "outlier.go",
      "function": "QuartileOutliers"
    },
    {
      "file": "extremes.go",
      "function": "ArgMax"
    },
    {
      "file": "cumulative.go",
      "function": "CumulativeMax"
    },
    {
      "file": "clip.go",
      "function": "Clip"
    },
    {
      "file": "rank.go",
      "function": "Rank"
    },
    {
      "file": "cumulative_sum.go",
      "function": "CumulativeSum"
    }
  ]
}
RCA
