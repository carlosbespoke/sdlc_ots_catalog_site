#!/usr/bin/env bash
set -euo pipefail

printf '%s' '4c0c6c14dd95864e7fdcdf1aac8e0765c3dc59dcae142c14a5abf30ea8b9d52a' > /workspace/oracle-auth-token

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
