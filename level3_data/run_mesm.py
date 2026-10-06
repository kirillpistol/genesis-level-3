"""Connect running MESM to a running compatible GENESIS node."""
import argparse,json,os
from pathlib import Path
from .mesm import MesmClient,DevLocalCoreClient,deliver

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mesm",default="http://127.0.0.1:8765")
    p.add_argument("--core",required=True)
    p.add_argument("--municipality",default="Сургут")
    p.add_argument("--output",type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--client-config");group.add_argument("--dev-local",action="store_true")
    a=p.parse_args()
    if a.dev_local:client=DevLocalCoreClient()
    else:
        from level1_core.discovery import client_from
        client=client_from(json.loads(Path(a.client_config).read_text(encoding="utf-8")))
    source=MesmClient(a.mesm,os.environ.get("MESM_API_TOKEN",""))
    results=deliver(source,client,a.core,a.municipality)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"MESM_GENESIS_results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    source.save_report(a.municipality,a.output/"MESM_report.html")
    print("MESM records delivered:",len(results),"; report:",a.output/"MESM_report.html")
if __name__=="__main__":main()
