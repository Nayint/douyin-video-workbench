"""Run explicitly once in the existing Dify API container; preserve draft graphs."""
import json
from sqlalchemy.orm import Session
from sqlalchemy import select
from app_factory import create_app
from extensions.ext_database import db
from models.account import Account
from models.model import App, ApiToken
from models.workflow import Workflow
from services.workflow_service import WorkflowService
from pathlib import Path

built=create_app(); app=built[1] if isinstance(built,tuple) else built
ids={'prototype':'97c51c93-653c-4d1d-a5d4-f1b82d500866','link':'ecf9a284-3a0a-4fb2-a994-6d8d2e601ce0'}
result={}; backups={}
with app.app_context():
    for mode,id in ids.items():
        with Session(db.engine,expire_on_commit=False) as s:
            a=s.get(App,id); account=s.get(Account,a.created_by)
            account.set_tenant_id_with_session(a.tenant_id,session=s)
            draft=s.scalar(select(Workflow).where(Workflow.app_id==id,Workflow.version=='draft'))
            backups[mode]={'app_id':id,'graph':draft.graph_dict,'features':draft.features}
            Path('/tmp/virallab-draft-backup.json').write_text(json.dumps(backups,ensure_ascii=False))
            if not a.workflow_id:
                published=WorkflowService().publish_workflow(session=s,app_model=a,account=account,
                    marked_name='ViralLab V1 接入',marked_comment='发布现有草稿，不修改节点')
                a.workflow_id=published.id
            token=s.scalar(select(ApiToken).where(ApiToken.app_id==id,ApiToken.type=='app'))
            if token is None:
                token=ApiToken(app_id=id,tenant_id=a.tenant_id,type='app',token=ApiToken.generate_api_key('app-',24,session=s));s.add(token)
            s.commit()
            result[mode]={'app_id':id,'api_key':token.token,'workflow_id':a.workflow_id}
Path('/tmp/virallab-provision.json').write_text(json.dumps(result))
print('VIRALLAB_PUBLICATION_COMPLETE',flush=True)
