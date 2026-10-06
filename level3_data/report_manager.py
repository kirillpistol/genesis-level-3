"""Collect separately approved report packages. Never merge source databases."""
import argparse,hashlib,html,json,os,re,uuid
from datetime import datetime,timezone
from pathlib import Path
from .mesm import MesmClient

ID=re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}")

def collect(config,output,client_factory=MesmClient):
    if config.get("contract")!="genesis.report-manager/1":raise ValueError("Unknown manager configuration")
    sources=config.get("sources",[])
    if not 1<=len(sources)<=100:raise ValueError("Expected 1..100 manually configured sources")
    ids=[s.get("node_id","") for s in sources]
    if len(set(ids))!=len(ids) or any(not ID.fullmatch(i) for i in ids):raise ValueError("Unique source IDs required")
    run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    run=Path(output)/run_id;run.mkdir(parents=True,exist_ok=False)
    results=[]
    for source in sources:
        entry={"source_node":source["node_id"],"municipality":source["municipality"],"status":"failed"}
        session=None;client=None
        try:
            env=source["token_env"]
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}",env):raise ValueError("Invalid token environment name")
            tls=source.get("tls",{})
            client=client_factory(source["origin"],os.environ.get(env,""),ca_file=tls.get("ca_file"),cert_file=tls.get("cert_file"),key_file=tls.get("key_file"))
            node=client.request("/v1/node")
            if node["node_id"]!=source["node_id"] or node["role"]!="L3":raise ValueError("Source identity mismatch")
            session=client.request("/v1/sessions/open",body={"municipality":source["municipality"],"snapshot_id":node["snapshot_id"]})
            package=client.request("/v1/report-package",{"municipality":source["municipality"],"session_id":session["session_id"]})
            if package["contract"]!="genesis.l3-report/1" or package["source_node"]!=source["node_id"] or package["municipality"]!=source["municipality"]:
                raise ValueError("Package ownership mismatch")
            if package["snapshot_id"]!=node["snapshot_id"]:raise ValueError("Source snapshot changed")
            report=package["report"]
            if report["format"]!="html" or hashlib.sha256(report["content"].encode()).hexdigest()!=report["sha256"]:
                raise ValueError("Report integrity mismatch")
            methodology=None
            if "methodology" in package:
                methodology=client.request("/v1/methodology")
                expected=package["methodology"]["methodology_id"]
                raw={k:v for k,v in methodology.items() if k!="methodology_id"}
                actual=hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                if methodology["methodology_id"]!=expected or actual!=expected or node.get("methodology_id")!=expected:
                    raise ValueError("Methodology snapshot mismatch")
            folder=run/source["node_id"];folder.mkdir()
            if methodology is not None:
                (folder/"methodology.json").write_text(json.dumps(methodology,ensure_ascii=False,indent=2),encoding="utf-8")
                entry["methodology_id"]=methodology["methodology_id"]
            (folder/"package.json").write_text(json.dumps(package,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
            (folder/"report.html").write_text(report["content"],encoding="utf-8")
            entry.update(status="collected",period=package["period"],snapshot_id=package["snapshot_id"],report_sha256=report["sha256"],report_file=source["node_id"]+"/report.html")
        except Exception as err:
            entry.update(error_kind=type(err).__name__,error="Package not collected; verify this source and its credentials")
        finally:
            if session is not None:
                try:
                    closed=client.request("/v1/sessions/close",body={"session_id":session["session_id"]})
                    entry["cycle_closed"]=closed["status"]=="closed"
                except Exception:
                    entry["cycle_closed"]=False;entry["session_cleanup"]="Close not confirmed; session expires on source"
            else:entry["cycle_closed"]=True
        results.append(entry)
    summary={"contract":"genesis.report-collection/1","run_id":run_id,"built_at":datetime.now(timezone.utc).isoformat(),"sources":results,"databases_merged":False,"raw_inputs_collected":False}
    (run/"collection.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    rows=[]
    for item in results:
        link='<a href="'+html.escape(item["report_file"],quote=True)+'">Открыть отчёт</a>' if item["status"]=="collected" else "Источник недоступен / пакет не принят"
        rows.append('<tr><td>'+html.escape(item["source_node"])+'</td><td>'+html.escape(item["municipality"])+'</td><td>'+html.escape(item["status"])+'</td><td>'+link+'</td></tr>')
    (run/"index.html").write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Комплект отчётов L3</title><style>body{font:16px Arial;max-width:1100px;margin:40px auto;color:#24272c}td,th{padding:14px;border-bottom:1px solid #ddd;text-align:left}table{width:100%}a{color:#4676c9}</style><h1>Комплект отчётов L3</h1><p>Каждый отчёт принадлежит своему источнику. Базы и показатели разных систем не объединяются.</p><table><tr><th>Источник</th><th>Муниципалитет</th><th>Статус</th><th>Отчёт</th></tr>'+''.join(rows)+'</table></html>',encoding="utf-8")
    return run,summary

def main():
    p=argparse.ArgumentParser(description="Independent L3 report manager; no GENESIS core startup")
    p.add_argument("--config",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    args=p.parse_args();config=json.loads(args.config.read_text(encoding="utf-8"))
    run,summary=collect(config,args.output)
    print("Report collection:",run/"index.html")
    if any(s["status"]!="collected" or not s["cycle_closed"] for s in summary["sources"]):raise SystemExit(2)
if __name__=="__main__":main()
