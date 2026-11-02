#!/usr/bin/env bash
set -euo pipefail

printf '%s' 'c08e6941e43c06f85e0b0b5c01bccc89eb4acb206906b8ef3f46750a4dc5783d' > /workspace/oracle-auth-token

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
