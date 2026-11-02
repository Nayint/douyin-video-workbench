import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_author_install_is_repeatable_and_does_not_overwrite(tmp_path):
    env={**os.environ,'HOME':str(tmp_path),'VIRALLAB_DATA':str(tmp_path/'data')}
    command=[sys.executable,str(ROOT/'scripts/configure_local.py'),'--install-author','--check']
    for _ in range(2):
        result=subprocess.run(command,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert '是皮皮呀' in result.stdout
    installed=tmp_path/'.codex/skills/pipi-copywriting/SKILL.md'
    assert installed.read_bytes()==(ROOT/'config/author-skills/pipi-copywriting/SKILL.md').read_bytes()
    installed.write_text('custom rule')
    result=subprocess.run(command,env=env,capture_output=True,text=True)
    assert result.returncode!=0
    assert installed.read_text()=='custom rule'


def test_invalid_dify_id_never_saves_configuration(tmp_path):
    result=subprocess.run([sys.executable,str(ROOT/'scripts/configure_local.py'),'--prototype-app-id','invalid'],
        env={**os.environ,'VIRALLAB_DATA':str(tmp_path)},capture_output=True,text=True)
    assert result.returncode!=0
    assert not (tmp_path/'settings.json').exists()


def test_dify_prepare_pins_revision_and_preserves_existing_settings(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('prepare_dify',ROOT/'scripts/prepare_dify.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**kw:module.REVISION+'\n')
    docker=tmp_path/'docker';docker.mkdir()
    (docker/'.env.example').write_text('EXPOSE_NGINX_PORT=80\nSECRET_KEY=old\n')
    source=tmp_path/'api/services';source.mkdir(parents=True)
    (source/'workflow_service.py').write_text('        if workflow and workflow.unique_hash != unique_hash:\n            pass\n')
    module.prepare(tmp_path)
    before=(docker/'.env').read_bytes()
    assert b'EXPOSE_NGINX_PORT=8081' in before and b'SECRET_KEY=old' not in before
    assert '127.0.0.1:8081:80' in (docker/'docker-compose.override.yaml').read_text()
    assert 'not graph.get("nodes")' in (docker/'virallab-workflow-service.py').read_text()
    with pytest.raises(SystemExit,match='已有 .env'):module.prepare(tmp_path)
    assert (docker/'.env').read_bytes()==before


def test_exported_workflow_keeps_runtime_contract_and_patch_nodes():
    from backend import dify_models
    assert dify_models.PRODUCT_REUSE_PATCH.is_file()
    spec=importlib.util.spec_from_file_location('reuse',dify_models.PRODUCT_REUSE_PATCH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for mode in ['prototype','link']:
        doc=yaml.safe_load((ROOT/f'deploy/dify/workflows/{mode}.yml').read_text())
        graph=doc['workflow']['graph']
        result=module.reuse_product_brief(graph)
        assert result['attachment_upload'] is False
        end=next(n for n in graph['nodes'] if n['data']['type']=='end')
        assert any(o['variable']=='final_copy' for o in end['data']['outputs'])
