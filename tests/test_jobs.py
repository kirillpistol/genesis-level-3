import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from level1_core.bindings import BindingPolicy,digest
from level1_core.runtime import Core
from level1_core.contracts import dumps
from level2_algorithms.numeric import Numeric
from level2_algorithms.packages import digest as package_digest
from level3_data.environment import verify_environment
from level3_data.jobs import JobRunner

class JobsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'component.py').write_bytes(b'# approved component\n')
        files={'component.py':hashlib.sha256((self.root/'component.py').read_bytes()).hexdigest()}
        self.package=dict(package_format='level2-package/1',level2_id='generic.numeric',algorithm_version=Numeric.version,model_version='manual/1',input_contract='numeric/1',package_sha256=package_digest(files),files=files)
        raw=b'10\n20\n'
        part=dict(part_id='p',source_id='s',origin='https://localhost:9443',size=len(raw),checksum=hashlib.sha256(raw).hexdigest(),record_hashes=[digest(10),digest(20)])
        self.manifest=dict(binding_id='generic',manifest_id='generic-data',data_version='1',input_contract='numeric/1',format='ndjson/1',parts=[part])
        specs={k:self.package[k] for k in ('algorithm_version','model_version','input_contract','package_sha256')}
        self.passport=dict(binding_id='generic',level2_id='generic.numeric',**specs,level3_manifest_id='generic-data',data_version='1',manifest_sha256=digest(self.manifest),allowed_workers=['w'])
        self.environment=dict(environment_format='level3-environment/1',environment_id='generic-env',environment_version='1',binding_id='generic',passport_sha256=digest(self.passport),adapter_contract='bound-stream/1',level2_package_sha256=self.package['package_sha256'],components=files)
        self.pin='a'*64
        policy=BindingPolicy(dict(bindings=[self.passport],data_grants={self.pin:['generic']}),{'generic':self.manifest})
        self.core=Core({'generic.numeric':Numeric},policy,{'generic.numeric':specs},'w');self.core.select_binding('generic')
        owner=self
        class Client:
            lost=False
            def request(self,endpoint,path,body=None,**kwargs):
                if path.endswith('/status'):return owner.core.binding_status(owner.pin)
                result=owner.core.process_bound(body,owner.pin)
                if self.lost:self.lost=False;raise TimeoutError('lost ACK')
                return result
        class Parts:
            def fetch(self,part):return raw
        self.client=Client()
        self.runner=JobRunner(self.client,'https://localhost',self.passport,self.manifest,Parts(),self.root,self.environment,self.root,self.package)
        self.job=dict(job_format='bound-job/1',job_id='job-1',binding_id='generic',passport_sha256=digest(self.passport),environment_sha256=digest(self.environment),expected_cursor=0,max_records=1,correlation_id='run-1')
    def tearDown(self):self.temp.cleanup()
    def test_partial_resume_result_and_complete(self):
        first=self.runner.run(self.job);self.assertEqual(first['checkpoint']['next_record'],1)
        self.assertFalse(first['complete'])
        second=self.runner.run(dict(self.job,job_id='job-2',expected_cursor=1))
        self.assertTrue(second['complete']);self.assertEqual(second['last_result']['result']['mean'],15)
        with self.assertRaises(ValueError):self.runner.run(self.job)
    def test_lost_ack_requires_confirmed_cursor(self):
        self.client.lost=True
        with self.assertRaises(TimeoutError):self.runner.run(self.job)
        with self.assertRaises(ValueError):self.runner.run(self.job)
        result=self.runner.run(dict(self.job,expected_cursor=1))
        self.assertEqual(result['checkpoint']['next_record'],2)
        self.assertEqual(self.core.algorithms['generic.numeric'].state()['n'],2)
    def test_wrong_identity_version_and_limits(self):
        for key,value in [('binding_id','other'),('passport_sha256','b'*64),('environment_sha256','c'*64),('expected_cursor',1),('max_records',65),('max_records',True)]:
            with self.assertRaises(ValueError):self.runner.run(dict(self.job,**{key:value}))
        self.assertEqual(self.core.binding['next_record'],0)
    def test_component_tampering_and_dependency(self):
        env=copy.deepcopy(self.environment);env['level2_package_sha256']='b'*64
        with self.assertRaises(ValueError):verify_environment(self.root,env,self.passport,self.root,self.package)
        (self.root/'component.py').write_text('altered')
        with self.assertRaises(ValueError):self.runner.run(self.job)
        self.assertEqual(self.core.binding['next_record'],0)
