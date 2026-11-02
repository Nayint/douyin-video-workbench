#!/bin/zsh
set -eu
cd "${0:A:h}"
./scripts/start.sh
/bin/zsh ./scripts/open-workbench.sh
