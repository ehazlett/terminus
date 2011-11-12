import unittest
import logging
import tempfile
import os
import shutil
from random import Random
import string
from subprocess import call, Popen, PIPE
import application
import settings
import utils
from utils import deploy
try:
    import simplejson as json
except ImportError:
    import json

def get_random_string():
    return ''.join(Random().sample(string.letters+string.digits, 16))

class CoreTestCase(unittest.TestCase):
    def setUp(self):
        self.client = application.app.test_client()

    def test_index(self):
        resp = self.client.get('/')
        assert(resp.status_code == 200 or resp.status_code == 302)

    def test_user_ops(self):
        test_user = get_random_string()
        test_role = get_random_string()
        # create
        assert utils.create_user(username=test_user, password='na', role=test_role)
        assert utils.get_user(test_user) != None
        # toggle
        assert utils.toggle_user(test_user, False)
        user_data = json.loads(utils.get_user(test_user))
        assert user_data['enabled'] == False
        assert utils.toggle_user(test_user, True)
        user_data = json.loads(utils.get_user(test_user))
        assert user_data['enabled'] == True
        assert utils.toggle_user(test_user)
        user_data = json.loads(utils.get_user(test_user))
        assert user_data['enabled'] == False
        # delete
        assert utils.delete_user(test_user)
        assert utils.get_user(test_user) == None
        assert utils.delete_role(test_role)
    
    def test_role_ops(self):
        test_role = get_random_string()
        assert utils.create_role(test_role)
        assert utils.get_role(test_role) != None
        assert utils.delete_role(test_role)
        assert utils.get_role(test_role) == None

    def tearDown(self):
        pass

class DeployTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_install_virtualenv(self):
        tmp_ve = get_random_string()
        tmp_ve_path = os.path.join(settings.VIRTUALENV_BASE_DIR, tmp_ve)
        tmp_reqs = tempfile.mktemp()
        with open(tmp_reqs, 'w') as f:
            f.write('flask')
        pkgs = ['requests']
        # test install
        deploy.install_virtualenv(application=tmp_ve, packages=pkgs, requirements=tmp_reqs)
        assert os.path.exists(tmp_ve_path)
        assert 'python' in os.listdir(os.path.join(tmp_ve_path, 'bin'))
        assert 'pip' in os.listdir(os.path.join(tmp_ve_path, 'bin'))
        p = Popen([os.path.join(os.path.join(tmp_ve_path, 'bin'), 'pip'), 'freeze'], stdout=PIPE, stderr=PIPE)
        p_out, p_err = p.stdout, p.stderr
        pip_freeze = p_out.read().lower()
        assert pip_freeze.find('requests') > -1
        assert pip_freeze.find('flask') > -1
        # cleanup
        shutil.rmtree(tmp_ve_path)
        os.remove(tmp_reqs)

    def test_install_virtualenv_custom_runtime(self):
        tmp_ve = get_random_string()
        tmp_ve_path = os.path.join(settings.VIRTUALENV_BASE_DIR, tmp_ve)
        tmp_reqs = tempfile.mktemp()
        with open(tmp_reqs, 'w') as f:
            f.write('flask')
        pkgs = ['requests']
        # test install
        deploy.install_virtualenv(application=tmp_ve, packages=pkgs, requirements=tmp_reqs, runtime='python2.6')
        assert os.path.exists(tmp_ve_path)
        assert 'python2.6' in os.listdir(os.path.join(tmp_ve_path, 'bin'))
        assert 'pip' in os.listdir(os.path.join(tmp_ve_path, 'bin'))
        p = Popen([os.path.join(os.path.join(tmp_ve_path, 'bin'), 'pip'), 'freeze'], stdout=PIPE, stderr=PIPE)
        p_out, p_err = p.stdout, p.stderr
        pip_freeze = p_out.read().lower()
        assert pip_freeze.find('requests') > -1
        assert pip_freeze.find('flask') > -1
        # cleanup
        shutil.rmtree(tmp_ve_path)
        os.remove(tmp_reqs)

    def tearDown(self):
        pass

if __name__=="__main__":
    unittest.main()
