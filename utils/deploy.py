#!/usr/bin/env python
import logging
from log import log_message
import uuid
from queue import task

@task
def deploy_app(package=None):
    """
    Deploys application

    :keyword package: Package to deploy (as tar.gz)

    """
    log_message(logging.INFO, 'root', 'Deploying package {0}'.format(package))
    data = {
        "status": "complete",
        "operation": "deploy_app",
    }
    return data

def install_virtualenv(application=None, packages=None):
    """
    Installs virtualenv for application

    Will also search application directory for a requirements.txt

    :keyword application: Virtualenv application
    :keyword packages: List of packages to install

    """
    log_message(logging.INFO, application, 'Installing virtualenv for {0}'.format(application))
    data = {
        "status": "complete",
        "operation": "install_virtualenv",
    }
    return data

def configure_appserver(application=None):
    """
    Configures application server (current uWSGI)

    :keyword application: Application to configure

    """
    log_message(logging.INFO, application, 'Configuring app server for {0}'.format(application))
    data = {
        "status": "complete",
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
