"""Read-only assembly verification of an already provisioned L3 environment."""
from level1_core.bindings import digest
from level1_core.contracts import check
from level2_algorithms.packages import verify_files,verify_package

FIELDS={'environment_format','environment_id','environment_version','binding_id','passport_sha256','adapter_contract','level2_package_sha256','components'}
def verify_environment(directory,descriptor,passport,package_directory,package):
    check('binding_passport',passport)
    if type(descriptor) is not dict or set(descriptor)!=FIELDS or descriptor['environment_format']!='level3-environment/1':raise ValueError('Invalid environment descriptor')
    for key in ('environment_id','environment_version'):
        if type(descriptor[key]) is not str or not 1<=len(descriptor[key])<=128:raise ValueError('Invalid environment identity')
    if descriptor['adapter_contract']!='bound-stream/1':raise ValueError('Unsupported adapter contract')
    if descriptor['binding_id']!=passport['binding_id'] or descriptor['passport_sha256']!=digest(passport):raise ValueError('Environment belongs to another binding')
    if descriptor['level2_package_sha256']!=passport['package_sha256']:raise ValueError('Wrong level 2 dependency')
    specs=verify_package(package_directory,package,passport)
    component_hash=verify_files(directory,descriptor['components'])
    return dict(ready=True,environment_id=descriptor['environment_id'],environment_version=descriptor['environment_version'],environment_sha256=digest(descriptor),components_sha256=component_hash,package_specs=specs)
