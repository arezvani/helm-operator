import kopf
import subprocess
import os 
import time
import asyncio
from kubernetes import client

REPO_NAME = os.getenv('REPO_NAME')
REPO_UPDATE_INTERVAL = os.getenv('REPO_UPDATE_INTERVAL')

def convertor(dd, separator ='.', prefix =''):
    return { prefix + separator + k if prefix else k : v
             for kk, vv in dd.items()
             for k, v in convertor(vv, separator, kk).items()
             } if isinstance(dd, dict) else { prefix : dd }

@kopf.on.create('servicecatalogues', retries=1)
def create_fn(body, spec, name, namespace, logger, **kwargs):
    chart_name = spec.get('name')
    version = spec.get('version')

    if not chart_name:
        raise kopf.PermanentError(f"Name must be set. Got {name!r}.")

    try:
        parameters = spec.get('parameters')
        parameters = convertor(parameters)
        parameters = ','.join(f'{k}={v}' for k, v in parameters.items())
        cmd = f'helm install -n {namespace} {name} {REPO_NAME}/{chart_name} --set {parameters}'

        if version:
            cmd += f'--version {version}'

        subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        logger.info(f"Service catalogue {namespace}/{chart_name}/{name} is created")
        kopf.info(body, reason='Create', message='Creation succeeded')
    
    except: 
        kopf.exception(body, reason='Create', message='Creation Failed')

@kopf.on.update('servicecatalogues', retries=1)
def update_fn(body, spec, name, namespace, logger, **kwargs):
    chart_name = spec.get('name')
    version = spec.get('version')
    
    if not chart_name:
        raise kopf.PermanentError(f"Name must be set. Got {name!r}.")
    
    try:
        parameters = spec.get('parameters')
        parameters = convertor(parameters)
        parameters = ','.join(f'{k}={v}' for k, v in parameters.items())
        cmd = f'helm upgrade -n {namespace} {name} {REPO_NAME}/{chart_name} --set {parameters}'

        if version:
            cmd += f'--version {version}'

        subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        logger.info(f"Service catalogue {namespace}/{chart_name}/{name} is updated")
        kopf.info(body, reason='Update', message='Update succeeded')
    
    except: 
        kopf.exception(body, reason='Update', message='Update Failed')

@kopf.on.delete('servicecatalogues', optional=True)
def delete_fn(body, spec, name, namespace, logger, **kwargs):
    try:
        chart_name = spec.get('name')
        cmd = f'helm uninstall -n {namespace} {name}'
        subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        patch_body = {'metadata': {'finalizers': []}}

        api_customobj: client.CustomObjectsApi = client.CustomObjectsApi()
        obj = api_customobj.patch_namespaced_custom_object(
            group='abriment.dev',
            version='v1',
            plural='servicecatalogues',
            namespace=namespace,
            name=name,
            body=patch_body
        )

        logger.info(f"Service catalogue {namespace}/{chart_name}/{name} is deleted")
        kopf.info(body, reason='Delete', message='Deletetion succeeded')

    except:
        kopf.exception(body, reason='Delete', message='Deletetion Failed')

@kopf.daemon('servicecatalogues')
async def monitor_kex_async(logger, **kwargs):
    while True:
        cmd = f'helm repo update {REPO_NAME}'
        subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        logger.info("Repo updated")
        await asyncio.sleep(int(REPO_UPDATE_INTERVAL))

def main(argv):
    loop = asyncio.get_event_loop()

    # Priority defines the priority/weight of this instance of the operator for
    # kopf peering. If there are multiple operator instances in the cluster,
    # only the one with the highest priority will actually be active.
    loop.run_until_complete(kopf.operator(
        clusterwide=True,
        priority=int(time.time()*1000000),
        peering_name="servicecatalogue-operator" # must be the same as the identified in ClusterKopfPeering
    ))

    return 0


if __name__ == "__main__":
    main([])