#!/bin/zsh
set -eu
service_target="gui/$(id -u)/local.virallab.workbench"
if launchctl print "$service_target" >/dev/null 2>&1; then
 service_pid=$(launchctl print "$service_target" | awk '/pid = / {print $3; exit}')
 launchctl bootout "$service_target"
 if [[ -n "$service_pid" ]]; then
  for attempt in {1..60}; do
   if ! kill -0 "$service_pid" 2>/dev/null; then break; fi
   sleep 0.2
  done
  if kill -0 "$service_pid" 2>/dev/null; then echo 'ViralLab 仍在退出，请稍后启动'; exit 1; fi
 fi
 echo 'ViralLab 已停止，数据保留；原有 Dify、Ollama 服务继续运行'
else
 echo 'ViralLab 服务当前未加载'
fi
