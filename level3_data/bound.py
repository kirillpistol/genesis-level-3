"""Operator-approved data manifest, mTLS part retrieval, exact bound delivery."""
import hashlib
import http.client
from pathlib import Path
from level1_core.bindings import digest,identifier
from level1_core.contracts import API_VERSION,check,dumps,loads
from level1_core.transport import context,origin,pins

class PartClient:
    def __init__(self,ca,cert,key,peers,timeout=3):
        self.context=context(ca,cert,key)
        self.peers={origin(url):pins(values) for url,values in peers.items()}
        if not 0<timeout<=30:raise ValueError('Timeout range')
        self.timeout=timeout
    def fetch(self,part):
        host,port=origin(part['origin'])
        if (host,port) not in self.peers:raise ValueError('Data origin not allowlisted')
        part_id=identifier(part['part_id'])
        conn=http.client.HTTPSConnection(host,port,context=self.context,timeout=self.timeout)
        try:
            conn.connect()
            pin=hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()
            if pin not in self.peers[(host,port)]:raise ValueError('Data server pin mismatch')
            conn.request('GET','/v1/data/parts/'+part_id)
            response=conn.getresponse()
            if response.status!=200 or response.getheader('Content-Type')!='application/x-ndjson':
                raise ValueError('Part rejected; redirects never followed')
            raw=response.read(65537)
            if len(raw)>65536:raise ValueError('Part too large')
            return raw
        finally:conn.close()

class BoundAdapter:
    def __init__(self,client,endpoint,passport,manifest,part_client):
        check('binding_passport',passport);check('data_manifest',manifest)
        if digest(manifest)!=passport['manifest_sha256']:raise ValueError('Manifest checksum mismatch')
        expected=dict(binding_id=passport['binding_id'],manifest_id=passport['level3_manifest_id'],
                      data_version=passport['data_version'],input_contract=passport['input_contract'])
        if any(manifest[k]!=v for k,v in expected.items()):raise ValueError('Wrong manifest for level 2 binding')
        self.client,self.endpoint=client,endpoint
        self.passport,self.manifest=loads(dumps(passport)),loads(dumps(manifest))
        self.part_client=part_client
    @classmethod
    def from_files(cls,client,endpoint,passport_path,manifest_path,part_client):
        for path in (passport_path,manifest_path):
            if Path(path).stat().st_size>1048576:raise ValueError('Metadata file too large')
        return cls(client,endpoint,loads(Path(passport_path).read_bytes()),loads(Path(manifest_path).read_bytes()),part_client)
    def _status(self):
        status=self.client.request(self.endpoint,'/v1/bindings/status')['binding']
        if status['passport']!=self.passport or status['passport_sha256']!=digest(self.passport):
            raise ValueError('Worker selected another binding/version')
        return status
    def message(self,part,index,record):
        passport=self.passport
        return dict(api_version=API_VERSION,binding_id=passport['binding_id'],manifest_id=passport['level3_manifest_id'],
                    data_version=passport['data_version'],manifest_sha256=passport['manifest_sha256'],input_contract=passport['input_contract'],
                    source_id=part['source_id'],part_id=part['part_id'],record_index=index,data=record)
    def deliver(self,correlation_id=None):
        """Resume from confirmed cursor. No automatic /tasks retries; one collector per binding."""
        position=self._status()['next_record'];total=sum(len(part['record_hashes']) for part in self.manifest['parts'])
        if not 0<=position<=total:raise ValueError('Invalid cursor')
        cursor=0
        for part in self.manifest['parts']:
            count=len(part['record_hashes'])
            if cursor+count<=position:cursor+=count;continue
            raw=self.part_client.fetch(part)
            if len(raw)!=part['size'] or hashlib.sha256(raw).hexdigest()!=part['checksum']:
                raise ValueError('Part size/checksum mismatch')
            lines=raw.splitlines()
            if len(lines)!=count:raise ValueError('Part record count mismatch')
            records=[loads(line) for line in lines]
            if any(digest(record)!=expected for record,expected in zip(records,part['record_hashes'])):
                raise ValueError('Part record hash mismatch')
            for index,record in enumerate(records):
                if cursor+index<position:continue
                message=self.message(part,index,record)
                options={} if correlation_id is None else dict(correlation_id=correlation_id)
                yield self.client.request(self.endpoint,'/v1/bindings/tasks',message,**options)
            cursor+=count
