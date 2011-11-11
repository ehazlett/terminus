#!/usr/bin/env python
from functools import wraps
from flask import g, session, redirect, url_for, request, current_app
from flask import flash
from flask import json
from flask import jsonify
import schema
import messages

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session or 'auth_token' not in session:
            flash(messages.ACCESS_DENIED, 'error')
            return redirect(url_for('index'))
        user_key = schema.USER_KEY.format(session['user'])
        user = g.db.get(user_key)
        user_data = json.loads(user)
        if 'role' not in user_data or user_data['role'].lower() != 'admin':
            flash(messages.ACCESS_DENIED, 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'auth_token' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'api_key' not in request.form:
            data = {'error': messages.NO_API_KEY}
            return jsonify(data)
        if request.form['api_key'] not in current_app.config['API_KEYS']:
            data = {'error': messages.INVALID_API_KEY}
            return jsonify(data)
        return f(*args, **kwargs)
    return decorated
