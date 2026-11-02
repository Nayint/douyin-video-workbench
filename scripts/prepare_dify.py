"""Prepare a separate, pinned Dify installation; never starts or replaces services."""
import argparse
from pathlib import Path
import secrets
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
REVISION='8387590ace4a094de812b7847fc6a4c3a27cd52b'


def prepare(source):
    source=source.resolve()
    if not source.exists():
        source.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['git','clone','--branch','1.17.1','--depth','1','https://github.com/langgenius/dify.git',str(source)],check=True)
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    if actual!=REVISION: raise SystemExit('Dify source revision mismatch; refusing to patch')
    docker=source/'docker';env=docker/'.env'
    if env.exists(): raise SystemExit('已有 .env；保留原配置。本脚本仅用于首次安装。')
    text=(docker/'.env.example').read_text()
    values={'EXPOSE_NGINX_PORT':'8081','EXPOSE_NGINX_SSL_PORT':'18443','ENABLE_COLLABORATION_MODE':'false'}
    for key in ('SECRET_KEY','DB_PASSWORD','REDIS_PASSWORD','SANDBOX_API_KEY','PLUGIN_DAEMON_KEY','INNER_API_KEY_FOR_PLUGIN'):
        values[key]=secrets.token_hex(32)
    lines=text.splitlines()
    for key,value in values.items():
        lines=[line for line in lines if not line.startswith(key+'=')]
        lines.append(key+'='+value)
    # Add the same five-line draft safeguard used by the original installation.
    original=source/'api/services/workflow_service.py'
    text=original.read_text()
    anchor='        if workflow and workflow.unique_hash != unique_hash:'
    if text.count(anchor)!=1: raise SystemExit('Dify source layout changed; refusing to patch')
    insert=('        # Reject a stale empty canvas replacing an existing draft.\n'
            '        if workflow and not graph.get("nodes") and workflow.graph_dict.get("nodes"):\n'
            '            raise WorkflowHashNotEqualError()\n\n')
    patch=docker/'virallab-workflow-service.py';patch.write_text(text.replace(anchor,insert+anchor))
    override=docker/'docker-compose.override.yaml'
    if override.exists(): raise SystemExit('已有 override；保留原配置，不覆盖')
    override.write_text('''services:
  nginx:
    ports: !override
      - "127.0.0.1:8081:80"
      - "127.0.0.1:18443:443"
  plugin_daemon:
    ports: !override
      - "127.0.0.1:5003:5003"
  ssrf_proxy:
    environment:
      SSRF_PROXY_ALLOW_PRIVATE_DOMAINS: "bilinote_bridge bilinote_opt_bridge"
  api:
    environment:
      ENABLE_COLLABORATION_MODE: "false"
    volumes:
      - ./virallab-workflow-service.py:/app/api/services/workflow_service.py:ro
  worker:
    environment:
      ENABLE_COLLABORATION_MODE: "false"
    volumes:
      - ./virallab-workflow-service.py:/app/api/services/workflow_service.py:ro
  api_websocket:
    environment:
      ENABLE_COLLABORATION_MODE: "false"
''')
    env.write_text('\n'.join(lines)+'\n');env.chmod(0o600)
    print('Dify 文件已准备（未启动容器）：'+str(docker))
    print('确认没有其他 dify-local 实例后，在该目录运行 docker compose -p dify-local up -d')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data/services/dify')
    prepare(parser.parse_args().source)
