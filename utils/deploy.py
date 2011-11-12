#!/usr/bin/env python
import logging
import os
from subprocess import call, Popen, PIPE
import shutil
import settings
import tempfile
import uuid
import tarfile
from queue import task
from log import log_message
try:
    import simplejson as json
except ImportError:
    import json

@task
def deploy_app(package=None):
    """
    Deploys application

    :keyword package: Package to deploy (as tar.gz)

    """
    log_message(logging.INFO, 'root', 'Deploying package {0}'.format(package))
    errors = {}
    output = {}
    tmp_deploy_dir = tempfile.mkdtemp()
    # extract
    try:
        tf = tarfile.open(package, mode="r:gz")
        tf.extractall(tmp_deploy_dir)
        # look for manifest
        manifest = os.path.join(tmp_deploy_dir, 'manifest.json')
        if os.path.exists(manifest):
            mdata = json.loads(open(manifest, 'r').read())
            if 'application' in mdata:
                app_name = mdata['application']
                if 'packages' in mdata:
                    pkgs = mdata['packages']
                else:
                    pkgs = None
                if os.path.exists(os.path.join(tmp_deploy_dir, 'requirements.txt')):
                    reqs = os.path.join(tmp_deploy_dir, 'requirements.txt')
                else:
                    reqs = None
                if 'runtime' in mdata:
                    runtime = mdata['runtime']
                else:
                    runtime = None
                if 'repo_type' in mdata:
                    repo_type = mdata['repo_type']
                else:
                    repo_type = None
                if 'repo_url' in mdata:
                    repo_url = mdata['repo_url'].lower()
                else:
                    repo_url = None
                if 'repo_revision' in mdata:
                    repo_revision = mdata['repo_revision']
                else:
                    repo_revision = None
                log_message(logging.DEBUG, app_name, mdata)
                # install app
                app_dir = os.path.join(settings.APPLICATION_BASE_DIR, app_name)
                if not os.path.exists(app_dir):
                    os.makedirs(app_dir)
                install_app_data = {}
                if repo_type and repo_url:
                    log_message(logging.DEBUG, app_name, 'Cloning {0} from {1} using {2}'.format(app_name, repo_url, repo_type))
                    install_app_data['repo_url'] = repo_url
                    if repo_type == 'git':
                        install_app_data['repo_init'] = 'Cloning with git'
                        p = Popen(['git', 'clone', repo_url], stdout=PIPE, stderr=PIPE, cwd=app_dir)
                    elif repo_type == 'hg':
                        p = Popen(['hg', 'clone', repo_url], stdout=PIPE, stderr=PIPE, cwd=app_dir)
                    if p:
                        p_out, p_err = p.stdout, p.stderr
                        install_app_data['repo_out'] = p_out.read()
                        install_app_data['repo_err'] = p_out.read()
                else:
                    log_message(logging.DEBUG, app_name, 'Installing application')
                    app_dir_target = os.path.join(app_dir, app_name)
                    if os.path.exists(app_dir_target):
                        shutil.rmtree(app_dir_target)
                    shutil.copytree(tmp_deploy_dir, app_dir_target)
                output['install_app'] = install_app_data
                # install ve
                output['install_virtualenv'] = install_virtualenv(application='demo', packages=pkgs, \
                    requirements=reqs, runtime=runtime)
            else:
                errors['deploy'] = 'invalid package manifest (missing application attribute)'
        else:
            log_message(logging.ERROR, 'root', 'Missing package manifest')
            errors['deploy'] = 'missing package manifest'
    except Exception, e:
        log_message(logging.ERROR, 'root', 'Deploy: {0}'.format(str(e)))
        errors['deploy'] = str(e)
    # cleanup
    if os.path.exists(tmp_deploy_dir):
        shutil.rmtree(tmp_deploy_dir)
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "deploy_app",
    }
    return data

def install_virtualenv(application=None, packages=None, requirements=None, runtime=None):
    """
    Installs virtualenv for application

    Will also search application directory for a requirements.txt

    :keyword application: Virtualenv application
    :keyword packages: List of packages to install
    :keyword requirements: (optional) Path to requirements.txt file
    :keyword runtime: (optional) Python runtime to use

    """
    log_message(logging.INFO, application, 'Installing virtualenv for {0}'.format(application))
    errors = {}
    output = {}
    # get ve target dir
    ve_target_dir = os.path.join(settings.VIRTUALENV_BASE_DIR, application)
    # create if needed
    if not os.path.exists(ve_target_dir):
        log_message(logging.DEBUG, application, 'Creating virtualenv in {0}'.format(ve_target_dir))
        if runtime:
            p = Popen(['which {0}'.format(runtime)], stdout=PIPE, stderr=PIPE, shell=True)
            (p_out, p_err) = (p.stdout, p.stderr)
            runtime_path = '/usr/local/bin/python2.6'
            p = Popen(['virtualenv', '--no-site-packages', '-p', runtime_path, ve_target_dir], stdout=PIPE, stderr=PIPE)
        else:
            p = Popen(['virtualenv', '--no-site-packages', ve_target_dir], stdout=PIPE, stderr=PIPE)
        (p_out, p_err) = (p.stdout, p.stderr)
        out = p_out.read()
        err = p_err.read()
        output['virtualenv_create_out'] = out
        output['virtualenv_create_err'] = err
    # install packages
    for pkg in packages:
        log_message(logging.DEBUG, application, 'Installing {0} in {1}'.format(pkg, ve_target_dir))
        p = Popen([os.path.join(os.path.join(ve_target_dir, 'bin'), 'pip'), 'install', '--use-mirrors', pkg], stdout=PIPE, stderr=PIPE)
        (p_out, p_err) = (p.stdout, p.stderr)
        out = p_out.read()
        err = p_err.read()
        output['virtualenv_{0}_out'.format(pkg)] = out
        output['virtualenv_{0}_err'.format(pkg)] = err
    if requirements and os.path.exists(requirements):
        log_message(logging.DEBUG, application, 'Installing packages via {0} requirements file in {1}'.format(requirements, ve_target_dir))
        p = Popen([os.path.join(os.path.join(ve_target_dir, 'bin'), 'pip'), 'install', '--use-mirrors', '-r', requirements], stdout=PIPE, stderr=PIPE)
        (p_out, p_err) = (p.stdout, p.stderr)
        out = p_out.read()
        err = p_err.read()
        output['virtualenv_requirements_out'.format(pkg)] = out
        output['virtualenv_requirements_err'.format(pkg)] = err
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "install_virtualenv",
    }
    log_message(logging.INFO, application, 'Virtualenv creation complete')
    return data

def configure_appserver(application=None):
    """
    Configures application server (current uWSGI)

    :keyword application: Application to configure

    """
    log_message(logging.INFO, application, 'Configuring app server for {0}'.format(application))
    errors = {}
    output = {}
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "configure_appserver",
    }
    return data

def configure_webserver(application=None):
    """
    Configures webserver (current Nginx)

    :keyword application: Application to configure

    """
    log_message(logging.INFO, application, 'Configuring webserver for {0}'.format(application))
    errors = {}
    output = {}
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "configure_webserver",
    }
    return data

def configure_supervisor(application=None):
    """
    Configures supervisord

    :keyword application: Application to configure

    """
    log_message(logging.INFO, application, 'Configuring supervisor for {0}'.format(application))
    errors = {}
    output = {}
    
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "configure_supervisor",
    }
    return data
