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
      "file": "/workspace/repo/igzip/igzip_inflate.c",
      "function": "isal_read_gzip_header"
    },
    {
      "file": "/workspace/repo/igzip/igzip_icf_base.c",
      "function": "isal_deflate_icf_finish_hash_map_base"
    },
    {
      "file": "/workspace/repo/igzip/igzip_icf_body.c",
      "function": "compress_icf_map_g"
    },
    {
      "file": "/workspace/repo/raid/raid_base.c",
      "function": "pq_gen_base"
    },
    {
      "file": "/workspace/repo/erasure_code/ec_base.c",
      "function": "gf_vect_mul_init_base"
    },
    {
      "file": "/workspace/repo/crc/crc64_base.c",
      "function": "crc64_jones_norm_base"
    },
    {
      "file": "/workspace/repo/igzip/flatten_ll.c",
      "function": "flatten_ll"
    },
    {
      "file": "/workspace/repo/igzip/igzip.c",
      "function": "isal_deflate_stateless"
    },
    {
      "file": "/workspace/repo/erasure_code/ec_highlevel_func.c",
      "function": "ec_encode_data_avx2"
    },
    {
      "file": "/workspace/repo/crc/crc_base.c",
      "function": "crc32_ieee_base"
    },
    {
      "file": "/workspace/repo/igzip/huff_codes.c",
      "function": "create_packed_dist_table"
    },
    {
      "file": "/workspace/repo/igzip/igzip_inflate.c",
      "function": "fixed_size_read"
    },
    {
      "file": "/workspace/repo/igzip/igzip_icf_body.c",
      "function": "icf_body_next_state"
    },
    {
      "file": "/workspace/repo/crc/crc64_base.c",
      "function": "crc64_jones_refl_base"
    },
    {
      "file": "/workspace/repo/igzip/igzip.c",
      "function": "flush_icf_block"
    },
    {
      "file": "/workspace/repo/crc/crc_base.c",
      "function": "crc32_iscsi_base"
    },
    {
      "file": "/workspace/repo/igzip/huff_codes.c",
      "function": "gen_huff_code_lens"
    }
  ]
}
RCA
