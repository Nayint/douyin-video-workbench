"""Run inside this machine's Dify 1.17.1 API container, via a fixed argv.

Use Dify's installed ORM/provider services to make immutable model-specific
versions. Never update the source app's workflow_id or its draft graph.
No credentials leave the container. Only local Ollama providers are supported.
"""
import hashlib
import json
import re
import sys
from uuid import UUID


def main():
    data = json.load(sys.stdin)
    app_id = str(UUID(data['app_id']))
    from app_factory import create_app
    _, application = create_app()
    with application.app_context():
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from extensions.ext_database import db
        from models.model import App
        from models.workflow import Workflow
        from services.app_dsl_service import AppDslService
        from services.model_provider_service import ModelProviderService
        from services.workflow_service import WorkflowService
        from services.workflow_version_number_service import allocate_version_number
        from graphon.model_runtime.entities.model_entities import ModelType
        from libs.datetime_utils import naive_utc_now

        with Session(db.engine) as session:
            app = session.get(App, app_id)
            if not app or not app.workflow_id:
                raise ValueError('未找到已发布的 Dify 工作流')
            source = session.get(Workflow, app.workflow_id)
            if not source or source.version == 'draft':
                raise ValueError('Dify 工作流尚未发布')
            graph = source.graph_dict
            nodes = [n for n in graph['nodes'] if n['data'].get('type') == 'llm']
            info = {'source_id': source.id, 'nodes': [
                {'id': n['id'], 'title': n['data'].get('title'),
                 'model': n['data'].get('model', {}).get('name'),
                 'vision': bool(n['data'].get('vision', {}).get('enabled'))}
                for n in nodes]}
            if data['action'] == 'run_models':
                from models.workflow import WorkflowNodeExecutionModel
                run_id = str(UUID(data['run_id']))
                records = session.scalars(select(WorkflowNodeExecutionModel).where(
                    WorkflowNodeExecutionModel.app_id == app.id,
                    WorkflowNodeExecutionModel.workflow_run_id == run_id,
                    WorkflowNodeExecutionModel.node_type == 'llm').order_by(WorkflowNodeExecutionModel.created_at)).all()
                result = []
                for record in records:
                    details = json.loads(record.process_data or '{}')
                    if details.get('model_name'):
                        result.append({'node_id': record.node_id, 'title': record.title,
                                       'model': details['model_name'], 'provider': details.get('model_provider')})
                return result
            if data['action'] == 'audit':
                return info
            if data['action'] == 'backup':
                return {**info, 'dsl': AppDslService.export_dsl(app, session=session,
                                                             include_secret=False, workflow_id=source.id)}
            if data['action'] != 'prepare' or source.id != data['source_id']:
                raise ValueError('原工作流已变化，请重新核对后创建模型版本')
            text, vision = data['text_model'], data['vision_model']
            fingerprint = hashlib.sha256(json.dumps(['model-versions-v3-product-brief', source.id, source.graph, text, vision],
                                                    ensure_ascii=False).encode()).hexdigest()
            marker = 'virallab-models:' + fingerprint
            existing = session.scalar(select(Workflow).where(Workflow.app_id == app.id,
                Workflow.marked_comment == marker, Workflow.version != 'draft'))
            if existing:
                return {'workflow_id': existing.id, 'source_id': source.id,
                        'text_model': text, 'vision_model': vision, 'product_reuse': {'version':'product-brief-reuse-v1','attachment_upload':False}}
            if not nodes:
                raise ValueError('此工作流没有可切换的 LLM 节点')
            product_reuse = reuse_product_brief(graph)
            nodes = [n for n in graph['nodes'] if n['data'].get('type') == 'llm']
            provider_service = ModelProviderService()
            registered = set()
            for node in nodes:
                config = node['data']
                model = config.get('model', {})
                provider = model.get('provider')
                if provider != 'langgenius/ollama/ollama' or config.get('model_selector'):
                    raise ValueError('此工作流包含非本地 Ollama 或动态模型节点，未进行自动切换')
                target = vision if config.get('vision', {}).get('enabled') else text
                if target not in registered:
                    bundle = provider_service._get_provider_configuration(app.tenant_id, provider)
                    configured = {m.model for m in bundle.get_provider_models(model_type=ModelType.LLM)}
                    if target not in configured:
                        credentials = bundle.get_current_credentials(model_type=ModelType.LLM, model=model['name'])
                        if not credentials:
                            raise ValueError('现有 Ollama 模型未配置可复用的本机连接')
                        provider_service.create_model_credential(app.tenant_id, provider, 'llm', target,
                                                               credentials.copy(), 'ViralLab 本机模型')
                    WorkflowService()._validate_llm_model_config(app.tenant_id, provider, target)
                    registered.add(target)
                model['name'] = target
            # The link workflow caches individual LLM stages. Namespace those
            # keys by both selected models so old-model outputs cannot be reused.
            for node in graph['nodes']:
                config = node['data']
                if config.get('type') == 'code' and config.get('title', '').startswith('查询') and '缓存' in config.get('title', ''):
                    def salt(match):
                        key = hashlib.sha256((match.group(2) + '|product-brief-reuse-v1|' + text + '|' + vision).encode()).hexdigest()
                        return 'json.dumps([' + json.dumps(key) + ',values]'
                    code, count = re.subn(r'json\.dumps\(\[([\"\x27])([0-9a-f]{64})\1\s*,\s*values\]', salt, config.get('code', ''))
                    if count != 1:
                        raise ValueError('工作流缓存规则已变化，未自动套用旧模型缓存')
                    config['code'] = code
            WorkflowService().validate_graph_structure(graph=graph)
            copy = Workflow.new(tenant_id=app.tenant_id, app_id=app.id, type=source.type,
                version=Workflow.version_from_datetime(naive_utc_now()),
                version_number=allocate_version_number(session=session, app_id=app.id),
                graph=json.dumps(graph, ensure_ascii=False), features=source.features,
                created_by=source.created_by, environment_variables=source.environment_variables,
                conversation_variables=source.conversation_variables,
                rag_pipeline_variables=source.rag_pipeline_variables,
                marked_name='ViralLab 产品正文复用版', marked_comment=marker)
            session.add(copy)
            session.commit()
            return {'workflow_id': copy.id, 'source_id': source.id,
                    'text_model': text, 'vision_model': vision, 'product_reuse': product_reuse}


if __name__ == '__main__':
    try:
        result = {'ok': True, 'data': main()}
    except Exception as error:
        # Internal exceptions can contain provider credentials; never print them.
        result = {'ok': False, 'error_type': type(error).__name__}
    print('VIRALLAB_RESULT=' + json.dumps(result, ensure_ascii=False))
