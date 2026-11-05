"""Real local AI acceptance on a dedicated empty browser workbench library."""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlparse
import uuid

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    parser.add_argument('--video', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target = urlparse(args.url)
    if target.scheme != 'http' or target.hostname not in ('localhost','127.0.0.1') or target.username or target.password:
        raise SystemExit('验收仅支持本机 HTTP 工作台')
    args.output.mkdir(parents=True, exist_ok=True)
    checks = []
    with httpx.Client(base_url=args.url, trust_env=False, timeout=180) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            assert response.status_code == 200, (path, response.status_code, response.text[:1000])
            return response.json()
        def wait(task):
            until, previous = time.monotonic() + 1200, ''
            while time.monotonic() < until:
                task = request('GET', '/api/tasks/' + task['id'])
                if task['stage'] != previous:
                    previous = task['stage']; print(task['kind'] + ': ' + previous, flush=True)
                if task['status'] == 'failed': raise AssertionError(task.get('error'))
                if task['status'] == 'succeeded': return task
                time.sleep(1)
            raise AssertionError('任务等待超时')
        assert not request('GET', '/api/cases') and not request('GET', '/api/products'), '请使用独立的空验收资料库'
        status = request('GET', '/api/setup/status')
        assert status['enabled'] and status['host'] == 'web'
        assert status['text_installed'] and status['vision_installed'] and status['whisper'], status
        if args.video:
            with args.video.open('rb') as stream:
                result = request('POST', '/api/cases/upload', data={'title':'虚构帆布袋 · 本机验收','auto_analyze':'true'},
                                 files={'file':('test-video.mp4',stream,'video/mp4')})
            task = wait(result['task'])
            case = request('GET', '/api/cases/' + result['case']['id'])
            assert case['transcript'].strip() and case['frames']
            assert {'video','cover_visual'}.issubset(task['result']['completed'])
            checks.append('上传有声视频、真实转写、文字和视觉分析')
        else:
            case = request('POST', '/api/cases', json={'title':'虚构帆布袋 · 文案验收',
                'transcript':'这款米白色帆布袋使用短提手，内侧有拉链小袋。先展示产品细节，再说明使用场景。'})
            wait(request('POST','/api/cases/'+case['id']+'/analyze',json={'type':'video','request_key':str(uuid.uuid4())}))
            checks.append('手动文案与真实结构分析')
        product = request('POST', '/api/products', json={'name':'米白色帆布袋', 'content':
            '产品名称：米白色帆布袋。颜色：米白色。材质：帆布。结构：短提手，内侧有一个拉链小袋。价格、尺寸、承重、防水性能、购买及使用经历均未提供，不得推断。'})
        for style in ('natural','author','reference'):
            payload = {'product_id':product['id'],'request_key':str(uuid.uuid4()),'draft_name':'本机验收 · '+style,
                'extra_requirements':'写60至90字的自然口语文案，只讲米白色、帆布、短提手和内侧拉链小袋，不写亲测经历、价格、尺寸、承重、防水或优惠。'}
            if style == 'author': payload['author_id'] = request('GET','/api/authors')[0]['id']
            if style == 'reference': payload['case_id'] = case['id']
            preview = request('POST','/api/dify/preview',json=payload)
            assert preview['mode'] == 'local'
            payload.update(expected_models=preview['model_selection'],expected_input_hash=preview['grounding']['hash'])
            task = wait(request('POST','/api/dify/generate',json=payload))
            assert task['result']['fact_check']['status'] == 'passed'
            response = client.get('/api/drafts/'+task['result']['draft_id']+'/export?format=txt')
            assert response.status_code == 200 and '帆布' in response.text
            assert not any(term in response.text for term in ('柔软','耐用','防水')), response.text
            (args.output / (style+'.txt')).write_text(response.text)
            checks.append(style+'：真实生成、逐句核对、保存和导出')
        report = {'passed':checks,'models':{key:status[key] for key in ('text_model','vision_model')},'data_path':status['data_path']}
        (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__ == '__main__': main()
