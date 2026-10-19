"""Register a private, immutable dedicated-server image after its CI push."""
import os
import re
import sys
from urllib.parse import quote

import requests


def required(name):
    value = os.environ.get(name,'').strip()
    if not value:
        raise ValueError('Configure '+name+'.')
    return value


def publish():
    key = required('EDGEGAP_API_KEY').removeprefix('token ')
    application = required('EDGEGAP_APPLICATION')
    image = required('EDGEGAP_IMAGE')
    version = required('GITHUB_SHA')
    if not image.startswith('registry.edgegap.com/') or ':' in image or '@' in image or not re.fullmatch(r'[0-9a-f]{40}',version):
        raise ValueError('Use a private Edgegap image without tag and a full source commit.')
    username = required('EDGEGAP_REGISTRY_USERNAME')
    password = required('EDGEGAP_REGISTRY_TOKEN')
    route = '/v1/app/'+quote(application,safe='')

    def call(method,path,payload=None,missing_ok=False):
        try:
            response=requests.request(method,'https://api.edgegap.com'+path,
                headers={'Authorization':'token '+key},json=payload,timeout=(5,45),allow_redirects=False)
            if response.status_code == 404 and missing_ok: return None
            if response.status_code not in (200,201,202):
                raise RuntimeError('Edgegap operation failed with HTTP '+str(response.status_code)+'. Inspect the dashboard configuration.')
            result=response.json()
            if not isinstance(result,dict): raise ValueError('Invalid provider response.')
            return result
        except requests.RequestException:
            raise RuntimeError('Edgegap did not respond. Check the existing version before rerunning publication.') from None

    if call('GET',route,missing_ok=True) is None:
        raise ValueError('Create the named Edgegap application in the dashboard before publishing a version.')
    previous=call('GET',route+'/version/'+version,missing_ok=True)
    if previous:
        if previous.get('docker_tag') != version or previous.get('docker_image') != image.split('/',1)[1]:
            raise ValueError('The existing immutable version refers to another image.')
    else:
        call('POST',route+'/version',{
            'name':version,'is_active':True,'req_cpu':1536,'req_memory':3072,'req_video':0,
            'docker_repository':'registry.edgegap.com','docker_image':image.split('/',1)[1],
            'docker_tag':version,'private_username':username,'private_token':password,
            'verify_image':True,'restart_policy':'never','max_duration':60,'time_to_deploy':180,
            'ports':[{'port':25000,'protocol':'UDP','name':'gameport','to_check':False}]})
    print('Registered Edgegap version '+version+'. Set Render EDGEGAP_VERSION to this value.')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf8') as output:
            output.write('Server published. Set Render `EDGEGAP_VERSION` to `'+version+'`.\n')


if __name__=='__main__':
    try: publish()
    except (ValueError,RuntimeError) as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)
