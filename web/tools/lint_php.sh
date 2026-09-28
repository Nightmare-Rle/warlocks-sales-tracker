#!/usr/bin/env bash
# Syntax check all PHP files with php -l (run from repo root)
# Usage: bash tools/lint_php.sh  (or from PowerShell after installing PHP)
set -e
files=$(find web -name '*.php')
for f in $files; do
  php -l "$f"
done
echo "All PHP files OK"