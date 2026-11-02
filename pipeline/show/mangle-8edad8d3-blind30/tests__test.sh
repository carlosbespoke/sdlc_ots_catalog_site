#!/usr/bin/env bash
# Single-container (shared) verifier entry point. Runs as root in the agent's own
# container after the agent phase. Writes one reward to /logs/verifier/reward.txt.
# The trap is a crash sentinel: if grading dies before writing a reward, the frame sees
# -1 rather than a stale or missing file. Absolute paths throughout, because Harbor may
# run this from any working directory.
set -uo pipefail
# Pin a trusted PATH for the whole grading pass. The grader runs as root and
# environment/Dockerfile puts the agent-owned /opt/venv/bin first on PATH, so every bare
# binary this script and grade.py resolve - python3 and tar here, setpriv/git/rm inside
# grade.py - would otherwise come from a directory the agent owns and could have planted a
# binary in, and run as root. /usr/local/bin:/usr/bin:/bin holds the base image's real
# tools, which are never chowned to the agent. The repository's own suite still gets the
# venv: grade.py runs it through a non-login, non-rc shell whose prelude sources only the
# root-owned /etc/profile.d, which re-prepends /opt/venv/bin for the agent command.
export PATH=/usr/local/bin:/usr/bin:/bin
# The agent phase's own processes are NOT killed here. In shared-verifier mode Harbor
# runs this script via `docker exec` into the still-running agent container, whose
# keep-alive/relay process runs as the agent account too; a uid-wide SIGKILL takes
# that down and the exec with it, so no reward is ever collected. The seal below and
# grade.py's seal_privileged_paths + restore + sabotage/canary/determinism checks are
# what defend a restored test from a process the agent left running.
# /logs/verifier COMES FROM THE AGENT PHASE, so it can be a SYMLINK the agent left behind,
# and every root operation in this script follows one: `mkdir -p` accepts a link that
# points at a directory, the `rm` below deletes through it, and the EXIT trap writes the
# crash sentinel through it. All three run BEFORE grade.py's seal_privileged_paths gets to
# replace it, so the seal cannot be what closes this - the first root-controlled operation
# has to. `-L` is the only test here that does not follow the link, and it is asked first
# so a DANGLING link (which `-e` calls absent) is caught too; a plain file by that name is
# not a directory to grade into either. `rm -f` and not `-rf`, so a real directory - the
# only legitimate case - is never what this deletes.
if [ -L /logs/verifier ] || { [ -e /logs/verifier ] && [ ! -d /logs/verifier ]; }; then rm -f /logs/verifier; fi
mkdir -p /logs/verifier
# /logs is shared with the agent phase, so a reward.txt can already be here, holding
# whatever the agent wrote. The trap below writes -1 only when the file is EMPTY, so an
# exit before grade.py writes its own reward would leave that number standing as the
# score; a DIRECTORY by that name is never empty to -s and takes no write at all. Nothing
# in this directory is this run's until this run writes it.
rm -rf /logs/verifier/reward.txt
trap 'if [ ! -s /logs/verifier/reward.txt ]; then echo -1 > /logs/verifier/reward.txt; fi' EXIT
# The interpreter is the base image's python (PATH excludes the agent's venv), run
# isolated: -S drops site processing (a planted sitecustomize.py or .pth), -I drops the
# environment (PYTHONPATH) and the user site. grade.py is stdlib-only, so it needs no venv.
# The repository's own suite, kept out of the agent's tree during its phase, is restored by
# grade.py itself (restore_hidden_suite) from the root-owned /tests mount, before it reads
# anything off the tree: that order is the point, and one file holds it.
python3 -S -I /tests/grade.py
