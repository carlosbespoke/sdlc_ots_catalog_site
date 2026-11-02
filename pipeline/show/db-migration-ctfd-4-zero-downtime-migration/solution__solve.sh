#!/bin/bash
# Reference solution: the migration files the database team wrote for this change (an overlay on the repository).
set -euo pipefail
cd /workspace/ctfd
cp -R /solution/repo/. /workspace/ctfd/
if [ -f /solution/repo-dotfiles.tar ]; then tar -xf /solution/repo-dotfiles.tar -C /workspace/ctfd; fi

git status --short | head -n 40
