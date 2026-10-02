"""Collect only the operator-selected binding and resume its confirmed cursor."""
import argparse
from pathlib import Path
from level1_core.bindings import digest
from level1_core.contracts import check,loads,dumps
from level1_core.discovery import client_from,Discovery
from .bound import BoundAdapter,PartClient

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--client-config',required=True)
    parser.add_argument('--parts-config',required=True)
    parser.add_argument('--passport',required=True)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--endpoint')
    args=parser.parse_args()
    config=loads(Path(args.client_config).read_bytes());client=client_from(config)
    passport=check('binding_passport',loads(Path(args.passport).read_bytes()))
    endpoint=args.endpoint or Discovery(client,config['endpoints']).choose_binding(passport['binding_id'],digest(passport))['endpoint']
    parts_config=loads(Path(args.parts_config).read_bytes());tls=parts_config['tls']
    part_client=PartClient(tls['ca'],tls['cert'],tls['key'],parts_config['peers'])
    adapter=BoundAdapter.from_files(client,endpoint,args.passport,args.manifest,part_client)
    for result in adapter.deliver():print(dumps(result).decode())
if __name__=='__main__':main()
