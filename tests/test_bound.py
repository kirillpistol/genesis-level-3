import copy
import hashlib
import unittest
from level1_core.bindings import digest
from level1_core.contracts import dumps
from level3_data.bound import BoundAdapter

class BoundTests(unittest.TestCase):
    def setUp(self):
        raw=b'10\n20\n'
        self.part=dict(part_id='p',source_id='s',origin='https://localhost:9443',size=len(raw),checksum=hashlib.sha256(raw).hexdigest(),record_hashes=[digest(10),digest(20)])
        self.manifest=dict(binding_id='a',manifest_id='a-data',data_version='1',input_contract='a/1',format='ndjson/1',parts=[self.part])
        self.passport=dict(binding_id='a',level2_id='a',algorithm_version='a/1',model_version='model/1',package_sha256='a'*64,input_contract='a/1',level3_manifest_id='a-data',data_version='1',manifest_sha256=digest(self.manifest),allowed_workers=['w'])
        owner=self
        class Parts:
            def __init__(self):self.calls=0;self.raw=raw
            def fetch(self,part):self.calls+=1;return self.raw
        class Client:
            def __init__(self):self.cursor=0;self.lost=False;self.records=[]
            def request(self,endpoint,path,body=None,**options):
                if path.endswith('/status'):return dict(binding=dict(passport=owner.passport,passport_sha256=digest(owner.passport),next_record=self.cursor))
                self.records.append(body['data']);self.cursor+=1
                if self.lost:self.lost=False;raise TimeoutError('Lost response after acceptance')
                return dict(result=body['data'])
        self.parts=Parts();self.client=Client()
        self.adapter=BoundAdapter(self.client,'https://localhost',self.passport,self.manifest,self.parts)
    def test_lost_ack_resumes_without_duplicate(self):
        self.client.lost=True
        with self.assertRaises(TimeoutError):list(self.adapter.deliver())
        self.assertEqual(list(self.adapter.deliver()),[dict(result=20)])
        self.assertEqual(self.client.records,[10,20])
        self.assertEqual(list(self.adapter.deliver()),[])
        self.assertEqual(self.parts.calls,2)
    def test_bad_part_rejected_before_sending(self):
        self.parts.raw=b'10\n99\n'
        with self.assertRaises(ValueError):list(self.adapter.deliver())
        self.assertEqual(self.client.records,[])
    def test_wrong_manifest_rejected(self):
        manifest=copy.deepcopy(self.manifest);manifest['data_version']='2'
        with self.assertRaises(ValueError):BoundAdapter(self.client,'https://localhost',self.passport,manifest,self.parts)
    def test_record_hash_checked_even_if_part_checksum_matches(self):
        manifest=copy.deepcopy(self.manifest);manifest['parts'][0]['record_hashes'][1]=digest(99)
        passport=copy.deepcopy(self.passport);passport['manifest_sha256']=digest(manifest)
        adapter=BoundAdapter(self.client,'https://localhost',passport,manifest,self.parts)
        self.passport=passport
        with self.assertRaises(ValueError):list(adapter.deliver())
        self.assertEqual(self.client.records,[])
