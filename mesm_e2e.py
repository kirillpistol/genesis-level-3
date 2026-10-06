"""Actual MESM SQLite -> authenticated API -> level 3 -> mTLS core -> level 2."""
import argparse,json,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer

def run(root):
 from mesm.access.store import build_store,DataStore
 from mesm.access.server import handler_factory
 from level1_core.runtime import Core
 from level1_core.server import Server,server_context
 from level1_core.discovery import client_from
 from level1_core.transport import PeerError
 from examples.make_test_certs import generate
 from level2_algorithms.mesm_budget import REGISTRY
 from level3_data.mesm import MesmClient,deliver
 with tempfile.TemporaryDirectory() as folder:
  temp=Path(folder);generate(temp/'certs');certs=temp/'certs'
  meta=build_store(root,temp/'mesm.sqlite');token='e2e-source-token-not-a-production-secret'
  source=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(DataStore(temp/'mesm.sqlite'),token,root))
  config=json.loads((certs/'server.json').read_text())
  core=Server(('127.0.0.1',0),Core(REGISTRY),server_context(config['tls']),client_roles=config['client_roles'])
  servers=[source,core];threads=[]
  try:
   for server in servers:
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();threads.append(thread)
   endpoint=f'https://localhost:{core.server_port}'
   def client(name):
    cfg=json.loads((certs/(name+'.json')).read_text());pin=next(iter(cfg['peers'].values()))
    cfg['peers']={endpoint:pin};return client_from(cfg)
   control=client('client');data=client('data')
   control.request(endpoint,'/v1/algorithms/attach',{'api_version':'1.0','name':'mesm_budget'})
   mesm=MesmClient(f'http://127.0.0.1:{source.server_port}',token)
   results=deliver(mesm,data,endpoint,'Сургут')
   assert len(results)==3
   result=next(r['result'] for r in results if r['result']['year']==2025)
   assert abs(result['calculated_deficit']-2241858.57535)<1e-6
   assert result['uncovered_plan_need']==0
   assert result['snapshot_id']==meta['snapshot_id']
   assert not result['early_warning_proven'] and not result['legal_compliance_proven']
   report=mesm.save_report('Сургут',temp/'report.html').read_text()
   assert 'Какую проблему решаем?' in report and 'Какие факты используем?' in report
   try:deliver(mesm,data,endpoint,'Unknown municipality')
   except ValueError:pass
   else:raise AssertionError('Unknown municipality accepted')
   try:data.request(endpoint,'/v1/algorithms/attach',{'api_version':'1.0','name':'numeric'})
   except PeerError as err:assert err.status==403
   else:raise AssertionError('Data role can attach')
   print(json.dumps(dict(connection='MESM -> GENESIS via mTLS',records=len(results),result_2025=result,report_downloaded=True,unknown_city_rejected=True,data_role_control_rejected=True),ensure_ascii=False,indent=2))
   return results
  finally:
   for server in servers:server.shutdown();server.server_close()
   for thread in threads:thread.join()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--mesm-root',type=Path,required=True);args=parser.parse_args();run(args.mesm_root.resolve())
