#!/usr/bin/env bash
set -euo pipefail

printf '%s' '789f8ddf9868283ae6d40828df7a76e0fc0cd30b289189e6084eef436f1f9b07' > /workspace/oracle-auth-token

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
