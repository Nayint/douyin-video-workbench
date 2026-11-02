#!/bin/zsh
set -eu
cd "${0:A:h:h}"
if [[ ! -f frontend/dist/index.html ]]; then echo '请先执行 cd frontend && npm ci && npm run build'; exit 1; fi
mkdir -p data
.venv/bin/python - <<'PY'
import plistlib
from pathlib import Path
root=Path.cwd()
config={'Label':'local.virallab.workbench','ProgramArguments':[str(root/'.venv/bin/python'),'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8765','--no-access-log'],
'WorkingDirectory':str(root),'RunAtLoad':True,'StandardOutPath':str(root/'data/server.log'),'StandardErrorPath':str(root/'data/server.log'),
'EnvironmentVariables':{'PATH':'/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin','HF_HUB_OFFLINE':'1'}}
with (root/'data/service.plist').open('wb') as f:plistlib.dump(config,f)
(root/'data/service.plist').chmod(0o600)
PY
service_domain="gui/$(id -u)"
if launchctl print "$service_domain/local.virallab.workbench" >/dev/null 2>&1; then
  launchctl kickstart "$service_domain/local.virallab.workbench"
else
  launchctl bootstrap "$service_domain" "$PWD/data/service.plist"
fi
for attempt in {1..40}; do
  if curl --noproxy '*' -fsS http://127.0.0.1:8765/api/health >/dev/null 2>&1; then echo 'ViralLab 已启动：http://127.0.0.1:8765'; exit 0; fi
  sleep 0.3
done
echo '启动失败，请查看 data/server.log'; exit 1
