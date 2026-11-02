"""Prepare optional third-party Apple reference model locally; no assets are redistributed.
Adapted from jadon7's MIT preparation script; see frontend/public/duo/licenses/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlretrieve
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,help='Your legally obtained original USDZ')
    parser.add_argument('--download',action='store_true',help='Download the original Apple USDZ for local preparation')
    parser.add_argument('--output',type=Path,default=ROOT/'frontend/public/duo/assets')
    args=parser.parse_args()
    if not args.archive and not args.download:parser.error('Provide --archive or explicitly choose --download')
    if args.output.exists():parser.error('Output directory already exists; preserving existing assets')
    try:from pxr import Sdf,Usd
    except ImportError:parser.error('Install optional usd-core==26.8 in a separate environment first')
    reference=json.loads((ROOT/'frontend/public/duo/sources.json').read_text())
    with tempfile.TemporaryDirectory(prefix='virallab-device-') as tmp:
        tmp=Path(tmp);archive=args.archive
        if not archive:
            archive=tmp/'model.usdz';urlretrieve(reference['model_source'],archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=reference['source_sha256']:
            parser.error('Original archive hash differs; refusing to prepare another asset version')
        assets=tmp/'assets';textures=assets/'textures';textures.mkdir(parents=True)
        with ZipFile(archive) as z:
            for name in z.namelist():
                if Path(name).suffix.lower() in {'.png','.jpg','.jpeg','.avif'}:
                    (textures/Path(name).name).write_bytes(z.read(name))
        stage=Usd.Stage.Open(str(archive.resolve()))
        stage.GetDefaultPrim().GetVariantSet('Pose').SetVariantSelection('Landscape')
        flattened=Usd.Stage.Open(stage.Flatten())
        for prim in flattened.Traverse():
            for attribute in prim.GetAttributes():
                value=attribute.Get()
                if isinstance(value,Sdf.AssetPath) and value.path:
                    filename=Path(value.path.split('[')[-1].rstrip(']')).name
                    attribute.Set(Sdf.AssetPath('textures/'+filename))
        output=assets/'iPhone_Duo_Render.usdc';flattened.GetRootLayer().Export(str(output))
        digest=hashlib.sha256(output.read_bytes()).hexdigest()
        print('Prepared USD hash:',digest)
        print('Reference hash match:',digest==reference['prepared_sha256'])
        args.output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(assets,args.output)
        print('Local assets prepared; third-party rights remain with their owners.')

if __name__=='__main__':main()
