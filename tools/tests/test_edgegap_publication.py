import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from publish_edgegap_version import publish


class EdgegapPublicationTests(unittest.TestCase):
    def settings(self):
        return {'EDGEGAP_API_KEY':'secret-management-token','EDGEGAP_APPLICATION':'kylr',
            'EDGEGAP_IMAGE':'registry.edgegap.com/example/kylr-server','GITHUB_SHA':'a'*40,
            'EDGEGAP_REGISTRY_USERNAME':'private-user','EDGEGAP_REGISTRY_TOKEN':'private-token',
            'GITHUB_STEP_SUMMARY':''}

    def response(self,status,body):
        result=Mock(status_code=status)
        result.json.return_value=body
        return result

    def test_registers_private_cpu_only_version_without_logging_credentials(self):
        responses=[self.response(200,{'name':'kylr'}),self.response(404,{}),self.response(201,{})]
        output=io.StringIO()
        with patch.dict(os.environ,self.settings()),patch('publish_edgegap_version.requests.request',side_effect=responses) as request,redirect_stdout(output):
            publish()
        payload=request.call_args.kwargs['json']
        self.assertEqual(payload['docker_tag'],'a'*40)
        self.assertEqual(payload['restart_policy'],'never')
        self.assertEqual(payload['ports'][0]['protocol'],'UDP')
        self.assertEqual(payload['req_video'],0)
        self.assertEqual(payload['private_token'],'private-token')
        self.assertNotIn('private-token',output.getvalue())
        self.assertNotIn('secret-management-token',output.getvalue())

    def test_never_overwrites_an_existing_immutable_version(self):
        responses=[self.response(200,{'name':'kylr'}),self.response(200,{'docker_tag':'other','docker_image':'example/kylr-server'})]
        with patch.dict(os.environ,self.settings()),patch('publish_edgegap_version.requests.request',side_effect=responses) as request:
            with self.assertRaises(ValueError): publish()
        self.assertEqual(request.call_count,2)

    def test_public_registry_is_rejected_before_any_network_access(self):
        settings=self.settings();settings['EDGEGAP_IMAGE']='docker.io/example/server'
        with patch.dict(os.environ,settings),patch('publish_edgegap_version.requests.request') as request:
            with self.assertRaises(ValueError): publish()
        request.assert_not_called()


if __name__=='__main__': unittest.main()
