#!/usr/bin/env python
import logging
import os
import traceback
import re
from subprocess import call, Popen, PIPE
import glob
import pwd
import grp
import shutil
import settings
import tempfile
import uuid
import tarfile
import utils
from queue import task
from utils import config
try:
    import simplejson as json
except ImportError:
    import json

@task
def deploy_app(app_name=None, package=None, build_ve=True, force_rebuild_ve=False):
    """
    Deploys application

    :keyword app_name: Name of application to deploy
    :keyword package: Package to deploy (as tar.gz)
    :keyword build_ve: Builds virtualenv for app
    :keyword force_rebuild_ve: Forces a rebuild of the virtualenv (destroys existing)

    """
    log = config.get_logger('deploy_app')
    log.info('Deploying package {0}'.format(package))
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
            if not app_name:
                if 'application' in mdata:
                    app_name = mdata['application']
            if not app_name:
                errors['deploy'] = 'Unspecified application name or missing in manifest'
            else:
                ## attempt to stop before deploy
                #stop_application(app_name)
                # get app config
                app_config = utils.get_application_config(app_name)
                if app_config:
                    try:
                        app_config = json.loads(app_config)
                    except:
                        app_config = {}
                else:
                    app_config = {}
                # create a uuid if non existent
                if 'uuid' not in app_config:
                    app_uuid = str(uuid.uuid4())
                    log.warn('UUID not found for {0}.  Assigning {1}'.format(app_name, app_uuid))
                    app_config['uuid'] = app_uuid
                if 'version' in mdata:
                    version = mdata['version']
                    log.info('Deploying version {0}'.format(version))
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
                log.debug(mdata)
                ## get app port
                #port_reserved = False
                #if 'port' in app_config:
                #    port = app_config['port']
                #    port_reserved = True
                #else:
                #    port = utils.get_next_application_port()
                #    app_config['port'] = port
                # get instances
                if 'instances' in app_config:
                    instances = app_config['instances']
                    if settings.NODE_NAME in instances:
                        instances = instances[settings.NODE_NAME]
                    else:
                        instances = []
                else:
                    instances = []
                if not instances:
                    new_port = utils.get_next_application_port()
                    instances.append(new_port)
                    utils.reserve_application_port(new_port)
                    log.debug('Reserved port {0} for {1}'.format(new_port, app_name))
                    app_config['instances'] = {}
                    app_config['instances'][settings.NODE_NAME] = instances
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
                    log.info('Cloning {0} from {1} using {2}'.format(app_name, repo_url, repo_type))
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
                        log.error('Unknown repo type: {0}'.format(repo_type))
                        p = None
                    if p:
                        p_out, p_err = p.stdout, p.stderr
                        install_app_data['repo_out'] = p_out.read()
                        install_app_data['repo_err'] = p_out.read()
                    # checkout revision if needed
                    if repo_revision:
                        log.info('{0}: checking out revision {1}'.format(app_name, repo_revision))
                        if repo_type == 'git':
                            p = Popen(['git', 'checkout', repo_revision], stdout=PIPE, stderr=PIPE, cwd=app_dir)
                        elif repo_type == 'hg':
                            p = Popen(['hg', 'checkout', repo_revision], stdout=PIPE, stderr=PIPE, cwd=app_dir)
                        else:
                            log.error('{0}: Unknown repo type: {0}'.format(app_name, repo_type))
                            p = None
                        if p:
                            os.waitpid(p.pid, 0)
                else:
                    log.debug('{0}: installing application'.format(app_name))
                    app_dir_target = os.path.join(app_dir, app_name)
                    shutil.copytree(tmp_deploy_dir, app_dir_target)
                output['install_app'] = install_app_data
                # install ve
                if build_ve:
                    output['install_virtualenv'] = install_virtualenv(application=app_name, packages=pkgs, \
                        requirements=reqs, runtime=runtime, force=force_rebuild_ve)
                # update app config
                utils.update_application_config(app_name, app_config)
                # configure supervisor
                output['configure_supervisor'] = configure_supervisor(application=app_name)
                output['configure_webserver'] = configure_webserver(application=app_name)
                # restart app
                restart_application(app_name)
        else:
            log.error('Missing package manifest')
            errors['deploy'] = 'missing package manifest'
    except Exception, e:
        traceback.print_exc()
        log.error('Deploy: {0}'.format(traceback.format_exc()))
        errors['deploy'] = str(e)
    # add app to node app list
    utils.add_app_to_node_app_list(app_name)
    # cleanup
    if os.path.exists(tmp_deploy_dir):
        shutil.rmtree(tmp_deploy_dir)
    log.info('Deployment for {0} complete'.format(app_name))
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
    log = config.get_logger('install_virtualenv')
    log.info('{0}: Installing virtualenv'.format(application))
    errors = {}
    output = {}
    # get ve target dir
    ve_target_dir = os.path.join(settings.VIRTUALENV_BASE_DIR, application)
    if force and os.path.exists(ve_target_dir):
        log.warn('{0}: Removing existing virtualenv'.format(application))
        shutil.rmtree(ve_target_dir)
    # create if needed
    if not os.path.exists(ve_target_dir):
        log.debug('{0}: Creating virtualenv in {1}'.format(application, ve_target_dir))
        if runtime:
            log.debug('{0}: Runtime {1} specified'.format(application, runtime))
            p = Popen(['which {0}'.format(runtime)], stdout=PIPE, stderr=PIPE, shell=True)
            p_out, p_err = p.stdout, p.stderr
            runtime_path = p_out.read()
            log.debug('{0}: Using runtime {1}'.format(application, runtime_path))
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
        log.debug('{0}: Installing {1} in {2}'.format(application, pkg, ve_target_dir))
        p = Popen([os.path.join(os.path.join(ve_target_dir, 'bin'), 'pip'), 'install', '--use-mirrors', pkg], stdout=PIPE, stderr=PIPE)
        os.waitpid(p.pid, 0)
        (p_out, p_err) = (p.stdout, p.stderr)
        out = p_out.read()
        err = p_err.read()
        output['virtualenv_{0}_out'.format(pkg)] = out
        output['virtualenv_{0}_err'.format(pkg)] = err
    if requirements and os.path.exists(requirements):
        log.debug('{0}: Installing packages via {1} requirements file in {2}'.format(application, requirements, ve_target_dir))
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
    log.info('{0}: Virtualenv creation complete'.format(application))
    return data

def configure_appserver(application=None):
    """
    Configures application server (current uWSGI)

    :keyword application: Application to configure

    """
    log = config.get_logger('configure_appserver')
    log.info('{0}: Configuring app server'.format(application))
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
    log = config.get_logger('configure_webserver')
    log.info('{0}: configuring webserver'.format(application))
    errors = {}
    output = {}
    app_config = utils.get_application_config(application)
    try:
        app_config = json.loads(app_config)
    except:
        raise RuntimeError('Invalid or missing application config')
    app_state_dir = os.path.join(settings.APPLICATION_STATE_DIR, application)
    for instance in app_config['instances'][settings.NODE_NAME]:
        # generate nginx config
        nginx_conf = os.path.join(settings.WEBSERVER_CONF_DIR, 'nginx_{0}_{1}.conf'.format(application, instance))
        conf = '# {0} config for application: {1} instance {2}\n'.format(settings.APP_NAME, application, instance)
        conf += 'user {0};\n'.format(settings.APPLICATION_USER)
        conf += 'worker_processes 1;\n'
        conf += 'error_log {0};\n'.format(os.path.join(settings.APPLICATION_LOG_DIR, '{0}_{1}-error.log'.format(application, 'nginx')))
        conf += 'pid {0};\n'.format(os.path.join(app_state_dir, 'nginx_{0}_{1}.pid'.format(application, instance)))
        conf += 'events {\n'
        conf += '  worker_connections 1024;\n'
        conf += '}\n'
        conf += 'http {\n'
        conf += '  include mime.types;\n'
        conf += '  default_type application/octet-stream;\n'
        conf += '  sendfile on;\n'
        conf += '  keepalive_timeout 65;\n'
        conf += '  server {\n'
        conf += '    listen {0};\n'.format(instance)
        conf += '    access_log {0};\n'.format(os.path.join(settings.APPLICATION_LOG_DIR, '{0}_{1}-access.log'.format(application, 'nginx')))
        conf += '    location /nginx-status {\n'
        conf += '      stub_status on;\n'
        conf += '    }\n'
        conf += '    location / {\n'
        conf += '      uwsgi_pass unix://{0};\n'.format(os.path.join(app_state_dir, '{0}_{1}.sock'.format(application, instance)))
        conf += '      include uwsgi_params;\n'
        conf += '    }\n'
        conf += '  }\n'
        conf += '}\n'
        # write config
        with open(nginx_conf, 'w') as f:
            f.write(conf)
        output['nginx_conf_{0}'.format(instance)] = conf
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
    log = config.get_logger('configure_supervisor')
    log.info('{0}: configuring supervisor'.format(application))
    errors = {}
    output = {}
    app_config = utils.get_application_config(application)
    try:
        app_config = json.loads(app_config)
    except:
        raise RuntimeError('Invalid or missing application config')
    app_dir = os.path.join(settings.APPLICATION_BASE_DIR, application)
    app_state_dir = os.path.join(settings.APPLICATION_STATE_DIR, application)
    app_local_dir = os.listdir(app_dir)[0]
    if not os.path.exists(app_state_dir):
        os.makedirs(app_state_dir)
    for instance in app_config['instances'][settings.NODE_NAME]:
        # generate uwsgi config
        supervisor_conf = os.path.join(settings.SUPERVISOR_CONF_DIR, 'uwsgi_{0}_{1}.conf'.format(application, instance))
        uwsgi_config = '[program:uwsgi_{0}_{1}]\n'.format(application, instance)
        uwsgi_config += 'command=uwsgi\n'
        # defaults
        uwsgi_config += '  --uid {0}\n'.format(settings.APPLICATION_USER)
        uwsgi_config += '  --gid {0}\n'.format(settings.APPLICATION_GROUP)
        uwsgi_config += '  -s {0}\n'.format(os.path.join(app_state_dir, '{0}_{1}.sock'.format(application, instance)))
        uwsgi_config += '  -H {0}\n'.format(os.path.join(settings.VIRTUALENV_BASE_DIR, application))
        uwsgi_config += '  -M\n'
        uwsgi_config += '  -C\n'
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
        uwsgi_config += 'redirect_stderr=true\n'
        uwsgi_config += 'stdout_logfile={0}/{1}.log\n'.format(settings.SUPERVISOR_CONF_DIR, application)
        uwsgi_config += 'stopsignal=QUIT\n'
        output['uwsgi_config_{0}'.format(instance)] = uwsgi_config
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
    log = config.get_logger('stop_application')
    log.info('{0}: stopping application'.format(app_name))
    errors = {}
    output = {}
    app_config = utils.get_application_config(app_name)
    try:
        app_config = json.loads(app_config)
    except:
        raise RuntimeError('Invalid or missing application config')
    for instance in app_config['instances'][settings.NODE_NAME]:
        # signal nginx to stop
        app_nginx_conf = os.path.join(settings.WEBSERVER_CONF_DIR, 'nginx_{0}_{1}.conf'.format(app_name, instance))
        if os.path.exists(app_nginx_conf):
            p = Popen(['nginx', '-c', app_nginx_conf, '-s', 'quit'], stdout=PIPE, stderr=PIPE)
            out, err = p.stdout.read().strip(), p.stderr.read().strip()
            if out != '':
                output['nginx_out_{0}'.format(instance)] = out
            if err != '':
                output['nginx_err_{0}'.format(instance)] = err
        # signal uwsgi to stop
        p = Popen(['supervisorctl', 'stop', 'uwsgi_{0}_{1}'.format(app_name, instance)], stdout=PIPE, stderr=PIPE)
        out, err = p.stdout.read().strip(), p.stderr.read().strip()
        if out != '':
            output['uwsgi_out_{0}'.format(instance)] = out
        if err != '':
            output['uwsgi_err_{0}'.format(instance)] = err
        # run fuser to kill anything else
        p = Popen(['fuser', '-k', os.path.join(settings.APPLICATION_BASE_DIR, app_name)], stdout=PIPE, stderr=PIPE)
        out, err = p.stdout.read().strip(), p.stderr.read().strip()
        if out != '':
            output['fuser_out'] = out
        if err != '':
            output['fuser_err'] = err
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
    log = config.get_logger('restart_application')
    errors = {}
    output = {}
    log.info('{0}: restarting application'.format(app_name))
    app_config = utils.get_application_config(app_name)
    try:
        app_config = json.loads(app_config)
    except:
        raise RuntimeError('Invalid or missing application config')
    # HACK: chown the state dir (and existing files)
    for f in glob.iglob('{0}'.format(settings.APPLICATION_STATE_DIR)):
        os.chown(f, pwd.getpwnam(settings.APPLICATION_USER).pw_uid, \
            grp.getgrnam(settings.APPLICATION_GROUP).gr_gid)
    for f in glob.iglob('{0}/*'.format(settings.APPLICATION_STATE_DIR)):
        os.chown(f, pwd.getpwnam(settings.APPLICATION_USER).pw_uid, \
            grp.getgrnam(settings.APPLICATION_GROUP).gr_gid)
    for f in glob.iglob('{0}/*/*'.format(settings.APPLICATION_STATE_DIR)):
        os.chown(f, pwd.getpwnam(settings.APPLICATION_USER).pw_uid, \
            grp.getgrnam(settings.APPLICATION_GROUP).gr_gid)
    # attempt to stop application first
    stop_application(app_name)
    # signal nginx to start
    for instance in app_config['instances'][settings.NODE_NAME]:
        app_nginx_conf = os.path.join(settings.WEBSERVER_CONF_DIR, 'nginx_{0}_{1}.conf'.format(app_name, instance))
        if os.path.exists(app_nginx_conf):
            p = Popen(['nginx', '-c', app_nginx_conf], stdout=PIPE, stderr=PIPE)
            out, err = p.stdout.read().strip(), p.stderr.read().strip()
            if out != '':
                output['nginx_out_{0}'.format(instance)] = out
            if err != '':
                output['nginx_err_{0}'.format(instance)] = err
        # signal uwsgi to stop
        p = Popen(['supervisorctl', 'start', 'uwsgi_{0}_{1}'.format(app_name, instance)], stdout=PIPE, stderr=PIPE)
        out, err = p.stdout.read().strip(), p.stderr.read().strip()
        if out != '':
            output['uwsgi_out_{0}'.format(instance)] = out
        if err != '':
            output['uwsgi_err_{0}'.format(instance)] = err
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "restart_application",
    }
    return data

@task
def remove_application(app_name=None):
    """
    Removes and application

    :keyword app_name: Name of application to remove

    """
    if not app_name:
        raise NameError('You must specify an application name')
    log = config.get_logger('remove_application')
    errors = {}
    output = {}
    if app_name not in utils.get_node_applications():
        raise NameError('Application not deployed to this node')
    app_config = utils.get_application_config(app_name)
    try:
        app_config = json.loads(app_config)
        # attempt to stop application first
        stop_application(app_name)
    except:
        pass # ignore errors on removal
    # remove configs
    app_state_dir = os.path.join(settings.APPLICATION_STATE_DIR, app_name)
    app_dir = os.path.join(settings.APPLICATION_BASE_DIR, app_name)
    ve_dir = os.path.join(settings.VIRTUALENV_BASE_DIR, app_name)
    if os.path.exists(app_state_dir):
        shutil.rmtree(app_state_dir)
        output['app_state_dir'] = 'removed'
    if os.path.exists(app_dir):
        shutil.rmtree(app_dir)
        output['app_dir'] = 'removed'
    if os.path.exists(ve_dir):
        shutil.rmtree(ve_dir)
        output['ve_dir'] = 'removed'
    # clear nginx configs
    for conf in os.listdir(settings.WEBSERVER_CONF_DIR):
        if re.search('{0}*'.format(app_name), conf):
            os.remove(os.path.join(settings.WEBSERVER_CONF_DIR, conf))
    output['nginx_configs'] = 'removed'
    # clear uwsgi configs
    for conf in os.listdir(settings.SUPERVISOR_CONF_DIR):
        if re.search('uwsgi_{0}*'.format(app_name), conf):
            os.remove(os.path.join(settings.SUPERVISOR_CONF_DIR, conf))
    output['uwsgi_configs'] = 'removed'
    # clear logs
    for log_file in os.listdir(settings.APPLICATION_LOG_DIR):
        if re.search('{0}*'.format(app_name), log_file):
            os.remove(os.path.join(settings.APPLICATION_LOG_DIR, log_file))
    # get app config to remove reserved instances
    if app_config:
        for instance in app_config['instances'][settings.NODE_NAME]:
            log.debug('{0}: releasing port: {1}'.format(app_name, instance))
            utils.release_application_port(instance)
    output['reserved_ports'] = 'released'
    # remove app config
    utils.remove_application_config(app_name)
    # remove from node app list
    utils.remove_app_from_node_app_list(app_name)
    # signal supervisor to update
    p = Popen(['supervisorctl', 'update'], stdout=PIPE, stderr=PIPE)
    p_out, p_err = p.stdout.read().strip(), p.stderr.read().strip()
    output['supervisorctl_out'] = p_out
    output['supervisorctl_err'] = p_err
    log.info('{0}: application removed'.format(app_name))
    data = {
        "status": "complete",
        "output": output,
        "errors": errors,
        "operation": "remove_application",
    }
    return data

@task
def scale_application(app_name=None, instances=None):
    """
    Scales application to number of instances

    :keyword app_name: Name of application to scale
    :keyword instances: Number of instances

    """
    if not app_name:
        raise NameError('You must specify an application name')
    log = config.get_logger('scale_application')
    errors = {}
    output = {}
    # attempt to stop application first
    stop_application(app_name)
    log.info('{0}: scaling application'.format(app_name))
    app_config = utils.get_application_config(app_name)
    try:
        app_config = json.loads(app_config)
    except:
        raise RuntimeError('Invalid or missing application config')


