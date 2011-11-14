#!/usr/bin/env python
import logging
import os
import traceback
from subprocess import call, Popen, PIPE
import shutil
import settings
import tempfile
import uuid
import tarfile
import utils
from queue import task
from log import log_message
try:
    import simplejson as json
except ImportError:
    import json

@task
def deploy_app(package=None, build_ve=True, force_rebuild_ve=False):
    """
    Deploys application

    :keyword package: Package to deploy (as tar.gz)
    :keyword build_ve: Builds virtualenv for app
    :keyword force_rebuild_ve: Forces a rebuild of the virtualenv (destroys existing)

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
                # attempt to stop before deploy
                stop_application(app_name)
                # get app config
                app_config = utils.get_application_config(app_name)
                if app_config:
                    try:
                        app_config = json.loads(app_config)
                    except:
                        app_config = {}
                else:
                    app_config = {}
                if 'version' in mdata:
                    version = mdata['version']
                    log_message(logging.INFO, app_name, 'Deploying version {0}'.format(version))
                else:
                    version = None
                app_config['version'] = version
                if 'packages' in mdata:
                    pkgs = mdata['packages']
                else:
                    pkgs = None
                app_config['packages'] = pkgs
                if os.path.exists(os.path.join(tmp_deploy_dir, 'requirements.txt')):
                    reqs = os.path.join(tmp_deploy_dir, 'requirements.txt')
                else:
                    reqs = None
                if 'runtime' in mdata:
                    runtime = mdata['runtime']
                else:
                    runtime = None
                app_config['runtime'] = runtime
                if 'repo_type' in mdata:
                    repo_type = mdata['repo_type']
                else:
                    repo_type = None
                app_config['repo_type'] = repo_type
                if 'repo_url' in mdata:
                    repo_url = mdata['repo_url'].lower()
                else:
                    repo_url = None
                app_config['repo_url'] = repo_url
                if 'repo_revision' in mdata:
                    repo_revision = mdata['repo_revision']
                else:
                    repo_revision = None
                app_config['repo_revision'] = repo_revision
                log_message(logging.DEBUG, app_name, mdata)
                # get app port
                port_reserved = False
                if 'port' in app_config:
                    port = app_config['port']
                    port_reserved = True
                else:
                    port = utils.get_next_application_port()
                    app_config['port'] = port
                # install app
                app_dir = os.path.join(settings.APPLICATION_BASE_DIR, app_name)
                if not os.path.exists(app_dir):
                    os.makedirs(app_dir)
                else:
                    # remove existing and re-create 
                    shutil.rmtree(app_dir)
                    os.makedirs(app_dir)
                install_app_data = {}
                if repo_type and repo_url:
                    log_message(logging.INFO, app_name, 'Cloning {0} from {1} using {2}'.format(app_name, repo_url, repo_type))
                    install_app_data['repo_url'] = repo_url
                    if repo_type == 'git':
                        install_app_data['repo_init'] = 'Cloning with git'
                        p = Popen(['git', 'clone', repo_url], stdout=PIPE, stderr=PIPE, cwd=app_dir)
                        os.waitpid(p.pid, 0)
                    elif repo_type == 'hg':
                        install_app_data['repo_init'] = 'Cloning with mercurial'
                        p = Popen(['hg', 'clone', repo_url], stdout=PIPE, stderr=PIPE,  cwd=app_dir)
                        os.waitpid(p.pid, 0)
                    else:
                        log_message(logging.ERROR, app_name, 'Unknown repo type: {0}'.format(repo_type))
                        p = None
                    if p:
                        p_out, p_err = p.stdout, p.stderr
                        install_app_data['repo_out'] = p_out.read()
                        install_app_data['repo_err'] = p_out.read()
                    # checkout revision if needed
                    if repo_revision:
                        log_message(logging.INFO, app_name, 'Checking out revision {0}'.format(repo_revision))
                        if repo_type == 'git':
                            p = Popen(['git', 'checkout', repo_revision], stdout=PIPE, stderr=PIPE, cwd=app_dir)
                        elif repo_type == 'hg':
                            p = Popen(['hg', 'checkout', repo_revision], stdout=PIPE, stderr=PIPE, cwd=app_dir)
                        else:
                            log_message(logging.ERROR, app_name, 'Unknown repo type: {0}'.format(repo_type))
                            p = None
                        if p:
                            os.waitpid(p.pid, 0)
                else:
                    log_message(logging.DEBUG, app_name, 'Installing application')
                    app_dir_target = os.path.join(app_dir, app_name)
                    shutil.copytree(tmp_deploy_dir, app_dir_target)
                output['install_app'] = install_app_data
                # install ve
                if build_ve:
                    output['install_virtualenv'] = install_virtualenv(application=app_name, packages=pkgs, \
                        requirements=reqs, runtime=runtime, force=force_rebuild_ve)
                # configure supervisor
                output['configure_supervisor'] = configure_supervisor(application=app_name)
                output['configure_webserver'] = configure_webserver(application=app_name, \
                    port=port)
                # update node port list
                if not port_reserved:
                    utils.reserve_application_port(port)
                # update app config
                utils.update_application_config(app_name, app_config)
                # restart app
                restart_application(app_name)
            else:
                errors['deploy'] = 'invalid package manifest (missing application attribute)'
        else:
            log_message(logging.ERROR, 'root', 'Missing package manifest')
            errors['deploy'] = 'missing package manifest'
    except Exception, e:
        log_message(logging.ERROR, 'root', 'Deploy: {0}'.format(traceback.format_exc()))

        errors['deploy'] = str(e)
    # cleanup
    if os.path.exists(tmp_deploy_dir):
        shutil.rmtree(tmp_deploy_dir)
    log_message(logging.INFO, 'root', 'Deployment for {0} complete'.format(app_name))
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "deploy_app",
    }
    return data

def install_virtualenv(application=None, packages=None, requirements=None, \
    runtime=None, force=False):
    """
    Installs virtualenv for application

    Will also search application directory for a requirements.txt

    :keyword application: Virtualenv application
    :keyword packages: List of packages to install
    :keyword requirements: (optional) Path to requirements.txt file
    :keyword runtime: (optional) Python runtime to use
    :keyword force: (optional) Forces build of virtualenv (destroys existing)

    """
    log_message(logging.INFO, application, 'Installing virtualenv for {0}'.format(application))
    errors = {}
    output = {}
    # get ve target dir
    ve_target_dir = os.path.join(settings.VIRTUALENV_BASE_DIR, application)
    if force and os.path.exists(ve_target_dir):
        log_message(logging.WARN, application, 'Removing existing virtualenv')
        shutil.rmtree(ve_target_dir)
    # create if needed
    if not os.path.exists(ve_target_dir):
        log_message(logging.DEBUG, application, 'Creating virtualenv in {0}'.format(ve_target_dir))
        if runtime:
            log_message(logging.DEBUG, application, 'Runtime {0} specified'.format(runtime))
            p = Popen(['which {0}'.format(runtime)], stdout=PIPE, stderr=PIPE, shell=True)
            p_out, p_err = p.stdout, p.stderr
            runtime_path = p_out.read()
            log_message(logging.DEBUG, application, 'Using runtime {0}'.format(runtime_path))
            p = Popen(['virtualenv', '--no-site-packages', '-p', runtime, ve_target_dir], stdout=PIPE, stderr=PIPE)
            os.waitpid(p.pid, 0)
        else:
            p = Popen(['virtualenv', '--no-site-packages', ve_target_dir], stdout=PIPE, stderr=PIPE)
            os.waitpid(p.pid, 0)
        (p_out, p_err) = (p.stdout, p.stderr)
        out = p_out.read()
        err = p_err.read()
        output['virtualenv_create_out'] = out
        output['virtualenv_create_err'] = err
    # install packages
    for pkg in packages:
        log_message(logging.DEBUG, application, 'Installing {0} in {1}'.format(pkg, ve_target_dir))
        p = Popen([os.path.join(os.path.join(ve_target_dir, 'bin'), 'pip'), 'install', '--use-mirrors', pkg], stdout=PIPE, stderr=PIPE)
        os.waitpid(p.pid, 0)
        (p_out, p_err) = (p.stdout, p.stderr)
        out = p_out.read()
        err = p_err.read()
        output['virtualenv_{0}_out'.format(pkg)] = out
        output['virtualenv_{0}_err'.format(pkg)] = err
    if requirements and os.path.exists(requirements):
        log_message(logging.DEBUG, application, 'Installing packages via {0} requirements file in {1}'.format(requirements, ve_target_dir))
        p = Popen([os.path.join(os.path.join(ve_target_dir, 'bin'), 'pip'), 'install', '--use-mirrors', '-r', requirements], stdout=PIPE, stderr=PIPE)
        os.waitpid(p.pid, 0)
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

def configure_webserver(application=None, port=None):
    """
    Configures webserver (current Nginx)

    :keyword application: Application to configure
    :keyword port: Port to use for webserver

    """
    log_message(logging.INFO, application, 'Configuring webserver for {0}'.format(application))
    errors = {}
    output = {}
    app_state_dir = os.path.join(settings.APPLICATION_STATE_DIR, application)
    # generate nginx config
    nginx_conf = os.path.join(settings.WEBSERVER_CONF_DIR, 'nginx_{0}.conf'.format(application))
    conf = '# {0} config for application: {1}\n'.format(settings.APP_NAME, application)
    conf += 'user {0};\n'.format(settings.APPLICATION_USER)
    conf += 'worker_processes 1;\n'
    conf += 'error_log {0};\n'.format(os.path.join(settings.APPLICATION_LOG_DIR, '{0}_{1}-error.log'.format(application, 'nginx')))
    conf += 'pid {0};\n'.format(os.path.join(app_state_dir, 'nginx_{0}.pid'.format(port)))
    conf += 'events {\n'
    conf += '  worker_connections 1024;\n'
    conf += '}\n'
    conf += 'http {\n'
    conf += '  include mime.types;\n'
    conf += '  default_type application/octet-stream;\n'
    conf += '  sendfile on;\n'
    conf += '  keepalive_timeout 65;\n'
    conf += '  server {\n'
    conf += '    listen {0};\n'.format(port)
    conf += '    access_log {0};\n'.format(os.path.join(settings.APPLICATION_LOG_DIR, '{0}_{1}-access.log'.format(application, 'nginx')))
    conf += '    location /nginx-status {\n'
    conf += '      stub_status on;\n'
    conf += '    }\n'
    conf += '    location / {\n'
    conf += '      uwsgi_pass unix://{0};\n'.format(os.path.join(app_state_dir, '{0}.sock'.format(application)))
    conf += '      include uwsgi_params;\n'
    conf += '    }\n'
    conf += '  }\n'
    conf += '}\n'
    # write config
    with open(nginx_conf, 'w') as f:
        f.write(conf)
    output['nginx_conf'] = conf
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "configure_webserver",
    }
    return data

def configure_supervisor(application=None, uwsgi_args={}):
    """
    Configures supervisord

    :keyword application: Application to configure

    """
    log_message(logging.INFO, application, 'Configuring supervisor for {0}'.format(application))
    errors = {}
    output = {}
    app_dir = os.path.join(settings.APPLICATION_BASE_DIR, application)
    app_state_dir = os.path.join(settings.APPLICATION_STATE_DIR, application)
    app_local_dir = os.listdir(app_dir)[0]
    if not os.path.exists(app_state_dir):
        os.makedirs(app_state_dir)
    # generate uwsgi config
    supervisor_conf = os.path.join(settings.SUPERVISOR_CONF_DIR, 'uwsgi_{0}.conf'.format(application))
    uwsgi_config = '[program:uwsgi_{0}]\n'.format(application)
    uwsgi_config += 'command=uwsgi\n'
    # defaults
    uwsgi_config += '  --uid {0}\n'.format(settings.APPLICATION_USER)
    uwsgi_config += '  --gid {0}\n'.format(settings.APPLICATION_GROUP)
    uwsgi_config += '  -s {0}\n'.format(os.path.join(app_state_dir, '{0}.sock'.format(application)))
    uwsgi_config += '  -H {0}\n'.format(os.path.join(settings.VIRTUALENV_BASE_DIR, application))
    uwsgi_config += '  -M\n'
    uwsgi_config += '  -p 2\n'
    uwsgi_config += '  --no-orphans\n'
    uwsgi_config += '  --vacuum\n'
    uwsgi_config += '  --harakiri 300\n'
    uwsgi_config += '  --max-requests 5000\n'
    uwsgi_config += '  --python-path {0}\n'.format(app_local_dir)
    uwsgi_config += '  -w wsgi\n'
    # uwsgi args
    for k,v in uwsgi_args.iteritems():
        uwsgi_config += '  --{0} {1}\n'.format(k, v)
    uwsgi_config += 'directory={0}\n'.format(os.path.join(settings.APPLICATION_BASE_DIR, \
        application))
    uwsgi_config += 'user={0}\n'.format(settings.APPLICATION_USER)
    uwsgi_config += 'stopsignal=QUIT\n'
    output['uwsgi_config'] = uwsgi_config
    # create config
    with open(supervisor_conf, 'w') as f:
        f.write(uwsgi_config)
    # signal supervisor to update
    p = Popen(['supervisorctl', 'update'], stdout=PIPE, stderr=PIPE)
    p_out, p_err = p.stdout.read().strip(), p.stderr.read().strip()
    output['supervisorctl_out'] = p_out
    output['supervisorctl_err'] = p_err
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "configure_supervisor",
    }
    return data

@task
def stop_application(app_name=None):
    """
    Stops an application

    :keyword app_name: Application to stop

    """
    if not app_name:
        raise NameError('You must specify an application name')
    log_message(logging.INFO, 'root', 'Stopping application {0}'.format(app_name))
    errors = {}
    output = {}
    # signal nginx to stop
    app_nginx_conf = os.path.join(settings.WEBSERVER_CONF_DIR, 'nginx_{0}.conf'.format(app_name))
    if os.path.exists(app_nginx_conf):
        p = Popen(['nginx', '-c', app_nginx_conf, '-s', 'quit'], stdout=PIPE, stderr=PIPE)
        out, err = p.stdout.read().strip(), p.stderr.read().strip()
        if out != '':
            output['nginx_out'] = out
        if err != '':
            output['nginx_err'] = err
    # signal uwsgi to stop
    p = Popen(['supervisorctl', 'stop', 'uwsgi_{0}'.format(app_name)], stdout=PIPE, stderr=PIPE)
    out, err = p.stdout.read().strip(), p.stderr.read().strip()
    if out != '':
        output['uwsgi_out'] = out
    if err != '':
        output['uwsgi_err'] = err
    # run fuser to kill anything else
    p = Popen(['fuser', '-k', os.path.join(settings.APPLICATION_BASE_DIR, app_name)], stdout=PIPE, stderr=PIPE)
    out, err = p.stdout.read().strip(), p.stderr.read().strip()
    if out != '':
        output['uwsgi_out'] = out
    if err != '':
        output['uwsgi_err'] = err

    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "stop_application",
    }
    return data

@task
def restart_application(app_name=None):
    """
    Restarts an application

    :keyword app_name: Name of application to restart

    """
    if not app_name:
        raise NameError('You must specify an application name')
    log_message(logging.INFO, 'root', 'Stopping application {0}'.format(app_name))
    errors = {}
    output = {}
    # attempt to stop application first
    stop_application(app_name)
    # signal nginx to start
    app_nginx_conf = os.path.join(settings.WEBSERVER_CONF_DIR, 'nginx_{0}.conf'.format(app_name))
    if os.path.exists(app_nginx_conf):
        p = Popen(['nginx', '-c', app_nginx_conf], stdout=PIPE, stderr=PIPE)
        out, err = p.stdout.read().strip(), p.stderr.read().strip()
        if out != '':
            output['nginx_out'] = out
        if err != '':
            output['nginx_err'] = err
    # signal uwsgi to stop
    p = Popen(['supervisorctl', 'start', 'uwsgi_{0}'.format(app_name)], stdout=PIPE, stderr=PIPE)
    out, err = p.stdout.read().strip(), p.stderr.read().strip()
    if out != '':
        output['uwsgi_out'] = out
    if err != '':
        output['uwsgi_err'] = err
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "start_application",
    }
    return data
