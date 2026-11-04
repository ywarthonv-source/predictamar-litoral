"""Download public sources from the audited manifest outside this repository.

Original snapshots can be dynamic: record checksum differences explicitly.
No credentials, restricted endpoints, or inference of permission to reuse.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request


def download(record,destination):
    name=record['file']
    if Path(name).name!=name:raise ValueError('Manifest filenames must be basenames')
    url=record['requested_url']
    if urllib.parse.urlsplit(url).scheme!='https':raise ValueError('HTTPS required')
    target=destination/name;temporary=destination/(name+'.part')
    receipt={'file':name,'requested_url':url,'retrieved_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'PredictaMAR public research audit/0.1'})
        with urllib.request.urlopen(request,timeout=60) as response,temporary.open('wb') as output:
            receipt.update(status=response.status,content_type=response.headers.get('Content-Type'))
            size=0
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>350*1024*1024:raise ValueError('Source exceeds per-file audit download limit')
                output.write(chunk)
        checksum=hashlib.file_digest(temporary.open('rb'),'sha256').hexdigest()
        receipt.update(bytes=temporary.stat().st_size,sha256=checksum,
                       checksum_matches_snapshot=checksum==record.get('sha256'))
        temporary.replace(target)
    except Exception as exc:
        receipt['error_type']=type(exc).__name__
        temporary.unlink(missing_ok=True)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,default=Path(__file__).parent/'research_2026_11_04/download_manifest.json')
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    if args.destination.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise SystemExit('Raw downloads must stay outside the public source repository')
    args.destination.mkdir(parents=True,exist_ok=True)
    records=json.loads(args.manifest.read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        receipts=list(pool.map(lambda record:download(record,args.destination),records))
    (args.destination/'download_receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'sources':len(receipts),'downloaded':sum('sha256' in r for r in receipts),
                      'changed_snapshots':sum(r.get('checksum_matches_snapshot') is False for r in receipts)}))
