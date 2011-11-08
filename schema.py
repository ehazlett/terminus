def user(username=None, first_name=None, last_name=None, email=None, \
    password=None, role=None, enabled=True):
    data = {
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'password': password,
        'role': role,
        'enabled': enabled,
    }
    return data

def role(rolename=None):
    return {'rolename': rolename}

def log(level=None, category='root', message=None):
    data = {
        'level': level,
        'category': category,
        'message': message,
    }
    return data
