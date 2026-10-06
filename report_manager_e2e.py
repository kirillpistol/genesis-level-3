"""Real HTTPS+mTLS source, external report manager, repeated closed cycles."""
import argparse,json,os,ssl,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer

def run(root):
 from examples.make_test_certs import generate
 from mesm.access.store import build_store,DataStore
 from mesm.access.server import handler_factory
 from level3_data.report_manager import collect
 with tempfile.TemporaryDirectory() as tmp:
  folder=Path(tmp);generate(folder/'certs');certs=folder/'certs'
  build_store(root,folder/'source.sqlite');token='source-cycle-e2e-local-token-12345'
  server=ThreadingHTTPServer(('127.0.0.1',0),handler_factory(DataStore(folder/'source.sqlite'),token,root))
  ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(certs/'server.crt',certs/'server.key');ctx.load_verify_locations(cafile=certs/'ca.crt');ctx.verify_mode=ssl.CERT_REQUIRED
  server.socket=ctx.wrap_socket(server.socket,server_side=True)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  env='MESM_L3_E2E_TOKEN';old=os.environ.get(env);os.environ[env]=token
  config={'contract':'genesis.report-manager/1','sources':[{'node_id':'mesm-surgut','municipality':'Сургут','origin':f'https://localhost:{server.server_port}','token_env':env,'tls':{'ca_file':str(certs/'ca.crt'),'cert_file':str(certs/'data.crt'),'key_file':str(certs/'data.key')}}]}
  try:
   runs=[collect(config,folder/'reports') for _ in range(2)]
   packages=[]
   for path,summary in runs:
    assert summary['sources'][0]['status']=='collected' and summary['sources'][0]['cycle_closed']
    assert not summary['databases_merged'] and not summary['raw_inputs_collected']
    packages.append(json.loads((path/'mesm-surgut/package.json').read_text()))
   assert packages[0]['snapshot_id']==packages[1]['snapshot_id']
   assert packages[0]['budget_calculations']==packages[1]['budget_calculations']
   print('PASS: independent MESM HTTPS/mTLS -> external manager; two completed cycles; stable financial results; no core startup or database merge')
  finally:
   if old is None:os.environ.pop(env,None)
   else:os.environ[env]=old
   server.shutdown();server.server_close();thread.join()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--mesm-root',type=Path,required=True);a=p.parse_args();run(a.mesm_root.resolve())
