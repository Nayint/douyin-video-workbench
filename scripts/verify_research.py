"""Additional real local-model checks, kept separate from the main flow."""
import json,time
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1]
c=httpx.Client(base_url='http://127.0.0.1:8765',trust_env=False,timeout=30)
report={}
for kind,material in [('title',{'titles':['桌上的东西不多，为什么总找不到笔？']}),('compare',{'titles':['桌上的东西不多，为什么总找不到笔？','先给常用文具一个固定位置']}),('suggest',{'product':'功能验收用虚构收纳盒：PP材质，20×10×8厘米，用于收纳桌面文具，不得编造销量或实际使用经历。'})]:
 r=c.post('/api/research',json={'type':kind,'material':material,'request_key':'qa-extra-'+kind});r.raise_for_status();id=r.json()['id'];end=time.monotonic()+900
 while time.monotonic()<end:
  t=c.get('/api/tasks/'+id).json()
  if t['status'] in ('succeeded','failed','interrupted'):break
  time.sleep(4)
 report[kind]={'status':t['status'],'error':t['error'],'result':t['result']};print(kind,t['status'],flush=True)
 (root/'data/qa/research.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 if t['status']!='succeeded':break
