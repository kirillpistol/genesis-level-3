import unittest
from level3_data.mesm import local_origin,MesmClient,deliver,decode
class Tests(unittest.TestCase):
 def test_only_loopback(self):
  for url in ("http://localhost:8765","http://127.0.0.1:8765/x","https://evil.example", "http://user@127.0.0.1:8765"):
   with self.assertRaises(ValueError):local_origin(url)
 def test_strict_json(self):
  for raw in ('{"a":1,"a":2}','{"a":NaN}'):
   with self.assertRaises(ValueError):decode(raw)
 def test_municipality_and_snapshot(self):
  client=MesmClient("http://127.0.0.1:8765","x"*24)
  def request(path,query=None):
   if path=="/v1/catalog":return dict(snapshot={"snapshot_id":"a"*64},datasets=[{"id":"budget_official_plan","evidence_status":"official_public"}])
   return dict(snapshot_id="b"*64,rows=[],total=0)
  client.request=request
  with self.assertRaises(ValueError):list(client.plans("Сургут"))
