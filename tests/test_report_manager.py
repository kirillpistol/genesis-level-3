import hashlib,json,os,tempfile,unittest
from pathlib import Path
from level3_data.report_manager import collect
class Tests(unittest.TestCase):
 def config(self):return {'contract':'genesis.report-manager/1','sources':[{'node_id':'mesm-a','municipality':'Город','origin':'https://source.example','token_env':'MESM_TEST_SOURCE'}]}
 def test_close_and_separate_output_on_success_and_failure(self):
  class Client:
   closed=0
   def __init__(self,*a,**kw):pass
   def request(self,path,query=None,body=None):
    if path=='/v1/node':return dict(node_id='mesm-a',role='L3',snapshot_id='a'*64)
    if path=='/v1/sessions/open':return dict(session_id='session')
    if path=='/v1/sessions/close':Client.closed+=1;return dict(status='closed')
    text='<h1>Отчёт</h1>'
    return dict(contract='genesis.l3-report/1',source_node='mesm-a',municipality='Город',period=2025,snapshot_id='a'*64,report=dict(format='html',content=text,sha256=hashlib.sha256(text.encode()).hexdigest()))
  with tempfile.TemporaryDirectory() as folder:
   run,res=collect(self.config(),folder,Client)
   self.assertEqual(res['sources'][0]['status'],'collected');self.assertTrue(res['sources'][0]['cycle_closed']);self.assertEqual(Client.closed,1)
   self.assertFalse(res['databases_merged']);self.assertTrue((run/'mesm-a/report.html').exists())
   old=Client.request
   def bad(self,path,query=None,body=None):
    if path=='/v1/report-package':raise ValueError('broken source')
    return old(self,path,query,body)
   Client.request=bad
   run,res=collect(self.config(),folder,Client)
   self.assertEqual(res['sources'][0]['status'],'failed');self.assertEqual(Client.closed,2)
 def test_duplicate_nodes_rejected(self):
  c=self.config();c['sources']*=2
  with self.assertRaises(ValueError):collect(c,'unused')
