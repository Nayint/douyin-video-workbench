#!/bin/zsh
set -eu
# A headless Chrome registered with LaunchServices can swallow ordinary URL opens.
# Select the user's normal profile explicitly and request a visible window.
if [[ -d '/Applications/Google Chrome.app' ]]; then
  /usr/bin/open -n -a '/Applications/Google Chrome.app' --args \
    "--user-data-dir=$HOME/Library/Application Support/Google/Chrome" \
    --new-window 'http://127.0.0.1:8765'
else
  /usr/bin/open 'http://127.0.0.1:8765'
fi
