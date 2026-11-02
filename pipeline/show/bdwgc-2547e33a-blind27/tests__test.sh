#!/usr/bin/env bash
# Verifier entry point, run as root in the separate (dual-container) verifier that
# tests/Dockerfile builds, after the agent phase.
# Writes one reward to /logs/verifier/reward.txt.
# The trap is a crash sentinel: if grading dies before writing a reward, the frame sees
# -1 rather than a stale or missing file. Absolute paths throughout, because Harbor may
# run this from any working directory.
set -uo pipefail
# Pin a trusted PATH for the whole grading pass. The grader runs as root and
# environment/Dockerfile (which tests/Dockerfile starts from) puts the agent-owned
# /opt/venv/bin first on PATH, so every bare binary this script and grade.py resolve -
# python3 and tar here, setpriv/git/rm inside grade.py - would otherwise come from a
# directory the agent account owns. The agent's own container never reaches this one, but
# grade.py runs the agent's adopted source as that account for every suite run, and that
# source could plant a binary there for root's next call. /usr/local/bin:/usr/bin:/bin
# holds the base image's real tools, which are never chowned to the agent. The
# repository's own suite still gets the venv: grade.py runs it through a non-login,
# non-rc shell whose prelude sources only the root-owned /etc/profile.d, which
# re-prepends /opt/venv/bin for the agent command.
export PATH=/usr/local/bin:/usr/bin:/bin
# No process kill here. The verifier container starts fresh, so no process of the agent
# phase exists in it; a uid-wide kill would also take down Harbor's own relay on a legacy
# shared-verifier task, which runs as the agent account. grade.py's seal, restore and
# sabotage/canary/determinism checks defend the restored suite from anything the adopted
# source starts during a suite run.
# /logs/verifier on a legacy shared-verifier task comes from the agent phase, so it can be
# a SYMLINK the agent left behind. A separate verifier's is Harbor's own fresh mount; the
# check costs nothing there and stays for the legacy case,
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
# On a legacy shared-verifier task /logs is shared with the agent phase, so a reward.txt
# can already be here, holding whatever the agent wrote. The trap below writes -1 only
# when the file is EMPTY, so an exit before grade.py writes its own reward would leave
# that number standing as the score; a DIRECTORY by that name is never empty to -s and
# takes no write at all. Nothing in this directory is this run's until this run writes it.
rm -rf /logs/verifier/reward.txt
trap 'if [ ! -s /logs/verifier/reward.txt ]; then echo -1 > /logs/verifier/reward.txt; fi' EXIT
# The interpreter is the base image's python (PATH excludes the agent's venv), run
# isolated: -S drops site processing (a planted sitecustomize.py or .pth), -I drops the
# environment (PYTHONPATH) and the user site. grade.py is stdlib-only, so it needs no venv.
# The repository's own suite, kept out of the agent's tree during its phase, is restored by
# grade.py itself (restore_hidden_suite) from the root-owned /tests, before it reads
# anything off the tree: that order is the point, and one file holds it.
python3 -S -I /tests/grade.py
