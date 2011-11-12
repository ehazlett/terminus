#!/usr/bin/env python
import logging
import os
from subprocess import call, Popen, PIPE
import settings
import tempfile
import uuid
from queue import task
from log import log_message

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
    # install ve
    output['install_virtualenv'] = install_virtualenv('demo', ['django'])
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

def configure_supervisor(application=None):
    """
    Configures supervisord

    :keyword application: Application to configure

    """
    log_message(logging.INFO, application, 'Configuring supervisor for {0}'.format(application))
    data = {
        "status": "complete",
        "operation": "configure_supervisor",
    }
    return data
