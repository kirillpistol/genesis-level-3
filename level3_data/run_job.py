"""Execute one generic bounded job against an already selected trusted core."""
import argparse
from pathlib import Path
from level1_core.bindings import digest
from level1_core.contracts import loads,dumps
from level1_core.discovery import client_from,Discovery
from .bound import PartClient
from .jobs import JobRunner

def read(path):
    with Path(path).open('rb') as stream:raw=stream.read(1048577)
    if len(raw)>1048576:raise ValueError('Descriptor size limit')
    return loads(raw)

def main():
    p=argparse.ArgumentParser()
    for name in ('client-config','parts-config','passport','manifest','directory','environment','package-directory','package','job'):p.add_argument('--'+name,required=True)
    p.add_argument('--endpoint');args=p.parse_args()
    config=read(args.client_config);client=client_from(config);passport=read(args.passport)
    endpoint=args.endpoint or Discovery(client,config['endpoints']).choose_binding(passport['binding_id'],digest(passport))['endpoint']
    parts_config=read(args.parts_config);tls=parts_config['tls']
    parts=PartClient(tls['ca'],tls['cert'],tls['key'],parts_config['peers'])
    runner=JobRunner(client,endpoint,passport,read(args.manifest),parts,args.directory,read(args.environment),args.package_directory,read(args.package))
    print(dumps(runner.run(read(args.job))).decode())
if __name__=='__main__':main()
