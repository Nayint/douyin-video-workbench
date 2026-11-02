"""Create synthetic demo records only in a dedicated empty data directory."""
import argparse, os, sys
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-dir',required=True,type=Path)
args=parser.parse_args()
directory=args.data_dir.expanduser().resolve()
if directory.exists() and any(directory.iterdir()): parser.error('演示目录必须为空，避免写入已有业务数据')
os.environ['VIRALLAB_DATA']=str(directory)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import core,jobs
core.init_db();core.save_settings({'vault_path':str(directory/'vault')})
for title,category,text in [('让产品细节自己说话','生活好物','这是一份虚构演示案例。先展示商品细节，再说明适用场景；不虚构使用体验。'),('把真实资料写成自然表达','创作方法','演示数据：将已知事实、未知信息与可展示动作分开，再组织文案。'),('从画面到文案，每一步有依据','视频研究','演示数据：保存关键帧、核对逐字稿，再研究结构，不凭空推断效果。')]:
 c=core.put('case',{'title':title,'category':category,'platform':'演示','tags':['演示数据'],'metrics':{'likes':None,'comments':None,'favorites':None,'shares':None}})
 jobs.save_transcript(c,text);jobs.case_note(core.get(c['id']))
note=core.sync_note('产品资料','demo-canvas-bag','示例帆布袋','演示资料：米白色、短提手、内侧拉链小袋。价格、容量、承重未知。')
core.put('product',{'name':'示例帆布袋 · 演示数据','note':note,'files':[]})
print('已生成虚构演示数据。启动时设置 VIRALLAB_DATA='+str(directory))
