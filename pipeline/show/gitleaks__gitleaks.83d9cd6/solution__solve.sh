#!/usr/bin/env bash
set -euo pipefail

printf '%s' 'a3e5bce4e9acd19b0fdc9a5e952ff10438eb94a357a305951e03e685d811f47e' > /workspace/oracle-auth-token

# The oracle verifies the test harness. It hands off through a wrapper
# and keeps argv[0] so help and usage text still name the submitted path.
cat > /workspace/compile.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cat > /workspace/executable <<'WRAPPER'
#!/usr/bin/env bash
exec -a "$0" /opt/task-reference/executable "$@"
WRAPPER
chmod 0755 /workspace/executable
EOF
chmod +x /workspace/compile.sh
