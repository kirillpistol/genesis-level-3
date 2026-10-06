"""Bound, resumable, operator-approved jobs over the existing core transport."""
import threading
from level1_core.bindings import digest,identifier
from level1_core.contracts import dumps
from .bound import BoundAdapter
from .environment import verify_environment

FIELDS={'job_format','job_id','binding_id','passport_sha256','environment_sha256','expected_cursor','max_records','correlation_id'}
class JobRunner:
    def __init__(self,client,endpoint,passport,manifest,part_client,directory,environment,package_directory,package):
        self.directory,self.environment=directory,environment
        self.package_directory,self.package=package_directory,package
        self.adapter=BoundAdapter(client,endpoint,passport,manifest,part_client)
        self.lock=threading.Lock()
        self.verify()
    def verify(self):
        return verify_environment(self.directory,self.environment,self.adapter.passport,self.package_directory,self.package)
    def run(self,job):
        if type(job) is not dict or set(job)!=FIELDS or job['job_format']!='bound-job/1':raise ValueError('Invalid job')
        identifier(job['job_id']);identifier(job['correlation_id'])
        if type(job['max_records']) is not int or not 1<=job['max_records']<=64:raise ValueError('Job record limit')
        if type(job['expected_cursor']) is not int or not 0<=job['expected_cursor']<=4096:raise ValueError('Invalid cursor')
        if job['binding_id']!=self.adapter.passport['binding_id'] or job['passport_sha256']!=digest(self.adapter.passport):raise ValueError('Job binding mismatch')
        if job['environment_sha256']!=digest(self.environment):raise ValueError('Job environment mismatch')
        if not self.lock.acquire(blocking=False):raise ValueError('Runner busy')
        try:
            readiness=self.verify() # detect modified components before every job
            before=self.adapter._status()['next_record']
            if before!=job['expected_cursor']:raise ValueError('Stale job cursor; inspect checkpoint before resubmitting')
            processed=0;last=None
            for result in self.adapter.deliver(correlation_id=job['correlation_id']):
                processed+=1;last=result
                if processed==job['max_records']:break
            after=self.adapter._status()['next_record']
            if after!=before+processed:raise ValueError('Concurrent collector detected')
            total=sum(len(part['record_hashes']) for part in self.adapter.manifest['parts'])
            response=dict(result_format='bound-job-result/1',job_id=job['job_id'],binding_id=job['binding_id'],correlation_id=job['correlation_id'],environment_sha256=readiness['environment_sha256'],processed=processed,checkpoint=dict(passport_sha256=job['passport_sha256'],next_record=after),complete=after==total,last_result=last)
            if len(dumps(response))>65536:raise ValueError('Result envelope limit; inspect confirmed cursor')
            return response
        finally:self.lock.release()
