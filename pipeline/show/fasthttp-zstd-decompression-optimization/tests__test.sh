#!/bin/sh
set -eu

# This explicit call also protects direct test.sh execution. The BASH_ENV entry
# in task.toml protects Harbor's earlier stdout redirection. Preparation is once
# per fresh single-step container; it never evaluates source as root.
/usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin \
    /usr/bin/python3 -S -E -B /opt/fasthttp-runtime/prepare_verifier.py

cleanup() {
    /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin \
        /usr/bin/python3 -S -E -B /opt/fasthttp-runtime/finalize_verifier.py || exit 125
}
trap cleanup EXIT

/usr/bin/setpriv --reuid=1001 --regid=1001 --clear-groups --no-new-privs \
    /usr/bin/env -i PATH=/usr/local/go/bin:/usr/bin:/bin \
    HOME=/home/verifier LANG=C.UTF-8 \
    /usr/bin/python3 -S -E -B /tests/grader.py
exit $?
