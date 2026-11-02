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
      "file": "/workspace/repo/cord/cordxtra.c",
      "function": "CORD_batched_chr_proc"
    },
    {
      "file": "/workspace/repo/fnlz_mlc.c",
      "function": "GC_finalized_disclaim"
    },
    {
      "file": "/workspace/repo/os_dep.c",
      "function": "GC_protect_heap"
    },
    {
      "file": "/workspace/repo/gcj_mlc.c",
      "function": "GC_init_gcj_malloc_mp"
    },
    {
      "file": "/workspace/repo/pthread_start.c",
      "function": "GC_pthread_start_inner"
    },
    {
      "file": "/workspace/repo/mark.c",
      "function": "GC_push_unconditionally"
    },
    {
      "file": "/workspace/repo/cord/cordprnt.c",
      "function": "extract_conv_spec"
    },
    {
      "file": "/workspace/repo/typd_mlc.c",
      "function": "GC_calloc_do_explicitly_typed"
    },
    {
      "file": "/workspace/repo/mallocx.c",
      "function": "GC_get_kind_and_size"
    },
    {
      "file": "/workspace/repo/cord/cordbscs.c",
      "function": "CORD_extend_path"
    },
    {
      "file": "/workspace/repo/ptr_chck.c",
      "function": "GC_same_obj"
    },
    {
      "file": "/workspace/repo/misc.c",
      "function": "GC_init_size_map"
    },
    {
      "file": "/workspace/repo/dbg_mlc.c",
      "function": "debug_free_zero"
    },
    {
      "file": "/workspace/repo/pthread_stop_world.c",
      "function": "GC_is_thread_suspended"
    },
    {
      "file": "/workspace/repo/cord/cordxtra.c",
      "function": "CORD_str"
    },
    {
      "file": "/workspace/repo/fnlz_mlc.c",
      "function": "GC_finalized_malloc"
    },
    {
      "file": "/workspace/repo/typd_mlc.c",
      "function": "GC_make_array_descriptor"
    },
    {
      "file": "/workspace/repo/mallocx.c",
      "function": "GC_realloc"
    },
    {
      "file": "/workspace/repo/ptr_chck.c",
      "function": "GC_is_valid_displacement"
    },
    {
      "file": "/workspace/repo/pthread_support.c",
      "function": "GC_release_mark_lock"
    },
    {
      "file": "/workspace/repo/malloc.c",
      "function": "GC_generic_malloc_inner_small"
    },
    {
      "file": "/workspace/repo/dyn_load.c",
      "function": "GC_register_dynlib_callback"
    },
    {
      "file": "/workspace/repo/reclaim.c",
      "function": "GC_reclaim_all"
    },
    {
      "file": "/workspace/repo/dbg_mlc.c",
      "function": "GC_store_debug_info_inner"
    },
    {
      "file": "/workspace/repo/mark.c",
      "function": "GC_push_marked"
    },
    {
      "file": "/workspace/repo/pthread_stop_world.c",
      "function": "GC_restart_all"
    },
    {
      "file": "/workspace/repo/malloc.c",
      "function": "GC_free_internal"
    }
  ]
}
RCA
