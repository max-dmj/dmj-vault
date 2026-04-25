import json
from functools import wraps
from uuid import uuid4

from flask import Flask, jsonify, request, session

from dmj_vault.dbaccess import db, APIKey, Admin, IPWhitelist

app = Flask(__name__)
app.secret_key = 'dmj-vault-admin-secret-change-me'


@app.before_request
def open_db():
    if db.is_closed():
        db.connect()


@app.teardown_appcontext
def close_db(exc):
    if not db.is_closed():
        db.close()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(force=True)
    login_val = data.get('login', '')
    password_val = data.get('password', '')

    try:
        admin = Admin.get(Admin.login == login_val)
    except Admin.DoesNotExist:
        return jsonify({'error': 'Invalid credentials'}), 403

    from werkzeug.security import check_password_hash
    if not check_password_hash(admin.password, password_val):
        return jsonify({'error': 'Invalid credentials'}), 403

    session['logged_in'] = True
    return jsonify({'ok': True})


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api-keys', methods=['GET'])
@login_required
def list_api_keys():
    keys = list(APIKey.select())
    result = []
    for k in keys:
        try:
            perms = json.loads(k.permissions)
        except (ValueError, TypeError):
            perms = {}
        result.append({
            'uid': k.uid,
            'is_valid': bool(k.is_valid),
            'ts_expires': k.ts_expires.isoformat() if k.ts_expires else None,
            'permissions_summary': list(perms.keys()),
        })
    return jsonify(result)


@app.route('/api-keys', methods=['POST'])
@login_required
def create_api_key():
    data = request.get_json(force=True)
    uid = str(uuid4())
    permissions = data.get('permissions', {})
    ts_expires = data.get('ts_expires', None)

    APIKey.create(
        uid=uid,
        permissions=json.dumps(permissions),
        ts_expires=ts_expires,
    )
    return jsonify({'uid': uid}), 201


@app.route('/api-keys/<uid>', methods=['GET'])
@login_required
def get_api_key(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        return jsonify({'error': 'Not found'}), 404

    whitelist = [
        {'id': w.id, 'src_ip_address': w.src_ip_address}
        for w in IPWhitelist.select().where(IPWhitelist.api_key_id == key.id)
    ]
    try:
        perms = json.loads(key.permissions)
    except (ValueError, TypeError):
        perms = {}

    return jsonify({
        'uid': key.uid,
        'is_valid': bool(key.is_valid),
        'ts_created': key.ts_created.isoformat() if key.ts_created else None,
        'ts_expires': key.ts_expires.isoformat() if key.ts_expires else None,
        'permissions': perms,
        'whitelist': whitelist,
    })


@app.route('/api-keys/<uid>/update', methods=['POST'])
@login_required
def update_api_key(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json(force=True)
    if 'is_valid' in data:
        key.is_valid = bool(data['is_valid'])
    if 'ts_expires' in data:
        key.ts_expires = data['ts_expires']
    if 'permissions' in data:
        key.permissions = json.dumps(data['permissions'])
    key.save()
    return jsonify({'ok': True})


@app.route('/api-keys/<uid>/delete', methods=['POST'])
@login_required
def delete_api_key(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        return jsonify({'error': 'Not found'}), 404

    IPWhitelist.delete().where(IPWhitelist.api_key_id == key.id).execute()
    key.delete_instance()
    return jsonify({'ok': True})


@app.route('/api-keys/<uid>/whitelist/add', methods=['POST'])
@login_required
def add_whitelist(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json(force=True)
    ip = data.get('src_ip_address', '').strip()
    if not ip:
        return jsonify({'error': 'src_ip_address required'}), 400

    entry = IPWhitelist.create(api_key_id=key.id, src_ip_address=ip)
    return jsonify({'id': entry.id}), 201


@app.route('/api-keys/<uid>/whitelist/<int:wl_id>/delete', methods=['POST'])
@login_required
def delete_whitelist(uid, wl_id):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        return jsonify({'error': 'Not found'}), 404

    try:
        entry = IPWhitelist.get(
            (IPWhitelist.id == wl_id) & (IPWhitelist.api_key_id == key.id))
    except IPWhitelist.DoesNotExist:
        return jsonify({'error': 'Not found'}), 404

    entry.delete_instance()
    return jsonify({'ok': True})
