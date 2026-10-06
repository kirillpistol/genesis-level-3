"""CLI preflight; no executable code loaded from descriptors."""
import argparse
from pathlib import Path
from level1_core.contracts import loads,dumps
from .environment import verify_environment

def main():
    p=argparse.ArgumentParser()
    for name in ('directory','environment','passport','package-directory','package'):p.add_argument('--'+name,required=True)
    args=p.parse_args()
    def read(path):
        with Path(path).open('rb') as stream:raw=stream.read(1048577)
        if len(raw)>1048576:raise ValueError('Descriptor size limit')
        return loads(raw)
    result=verify_environment(args.directory,read(args.environment),read(args.passport),args.package_directory,read(args.package))
    print(dumps(result).decode())
if __name__=='__main__':main()
