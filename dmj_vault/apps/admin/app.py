import json
from datetime import datetime
from functools import wraps
from uuid import uuid4

from flask import Flask, jsonify, redirect, render_template, request, session, flash, url_for
from flask_session import Session

from dmj_vault.dbaccess import db, APIKey, Admin, IPWhitelist

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dmj-vault-admin-secret-change-me'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/var/run/dmj-vault/sessions'
Session(app)


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


def ui_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('ui_login'))
        return f(*args, **kwargs)
    return decorated


# ── JSON API ──────────────────────────────────────────────────────────────────

@app.route('/login', methods=['POST'])
def login():
    if request.content_type and 'application/json' in request.content_type:
        data = request.get_json(force=True)
        login_val = data.get('login', '')
        password_val = data.get('password', '')
    else:
        login_val = request.form.get('login', '')
        password_val = request.form.get('password', '')

    from werkzeug.security import check_password_hash
    try:
        admin = Admin.get(Admin.login == login_val)
    except Admin.DoesNotExist:
        admin = None

    if admin is None or not check_password_hash(admin.password, password_val):
        if request.content_type and 'application/json' in request.content_type:
            return jsonify({'error': 'Invalid credentials'}), 403
        return render_template('login.html', error='Invalid credentials')

    session['logged_in'] = True
    if request.content_type and 'application/json' in request.content_type:
        return jsonify({'ok': True})
    return redirect(url_for('ui_keys'))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    if request.content_type and 'application/json' in request.content_type:
        return jsonify({'ok': True})
    return redirect(url_for('ui_login'))


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
            'name': k.name,
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
    name = data.get('name', '')
    permissions = data.get('permissions', {})
    ts_expires = data.get('ts_expires', None)

    APIKey.create(
        uid=uid,
        name=name,
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
        'name': key.name,
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
    if 'name' in data:
        key.name = data['name']
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


# ── HTML UI ───────────────────────────────────────────────────────────────────

@app.route('/')
def ui_root():
    if session.get('logged_in'):
        return redirect(url_for('ui_keys'))
    return redirect(url_for('ui_login'))


@app.route('/login', methods=['GET'])
def ui_login():
    if session.get('logged_in'):
        return redirect(url_for('ui_keys'))
    return render_template('login.html', error=None)


@app.route('/logout', methods=['GET'])
def ui_logout():
    session.clear()
    return redirect(url_for('ui_login'))


@app.route('/keys')
@ui_login_required
def ui_keys():
    keys = list(APIKey.select().order_by(APIKey.ts_created.desc()))
    for k in keys:
        try:
            perms = json.loads(k.permissions)
        except (ValueError, TypeError):
            perms = {}
        k.permissions_summary = [f'{s}:{a}' for s, a in perms.items()]
    return render_template('keys.html', keys=keys)


@app.route('/keys/new', methods=['GET'])
@ui_login_required
def ui_keys_new():
    return render_template('key_detail.html',
                           uid=None, is_valid=False, name='',
                           ts_created=None, ts_expires_local='',
                           permissions_json='{}', whitelist=[])


@app.route('/keys/new', methods=['POST'])
@ui_login_required
def ui_keys_new_post():
    uid = str(uuid4())
    name = request.form.get('name', '').strip()
    perms = _parse_permissions_form()
    ts_expires = _parse_ts_expires()
    APIKey.create(uid=uid, name=name, permissions=json.dumps(perms), ts_expires=ts_expires)
    flash('Key created.', 'success')
    return redirect(url_for('ui_key_detail', uid=uid))


@app.route('/keys/<uid>')
@ui_login_required
def ui_key_detail(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        flash('Key not found.', 'error')
        return redirect(url_for('ui_keys'))

    whitelist = list(IPWhitelist.select().where(IPWhitelist.api_key_id == key.id))
    try:
        perms = json.loads(key.permissions)
    except (ValueError, TypeError):
        perms = {}

    ts_expires_local = ''
    if key.ts_expires:
        ts_expires_local = key.ts_expires.strftime('%Y-%m-%dT%H:%M')

    return render_template('key_detail.html',
                           uid=key.uid,
                           is_valid=bool(key.is_valid),
                           name=key.name,
                           ts_created=key.ts_created,
                           ts_expires_local=ts_expires_local,
                           permissions_json=json.dumps(perms),
                           whitelist=whitelist)


@app.route('/keys/<uid>/save', methods=['POST'])
@ui_login_required
def ui_key_save(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        flash('Key not found.', 'error')
        return redirect(url_for('ui_keys'))

    key.name = request.form.get('name', '').strip()
    key.permissions = json.dumps(_parse_permissions_form())
    key.ts_expires = _parse_ts_expires()
    key.save()
    flash('Saved.', 'success')
    return redirect(url_for('ui_key_detail', uid=uid))


@app.route('/keys/<uid>/toggle', methods=['POST'])
@ui_login_required
def ui_key_toggle(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        flash('Key not found.', 'error')
        return redirect(url_for('ui_keys'))

    key.is_valid = not bool(key.is_valid)
    key.save()
    flash('Key ' + ('activated.' if key.is_valid else 'deactivated.'), 'success')
    return redirect(url_for('ui_key_detail', uid=uid))


@app.route('/keys/<uid>/delete', methods=['POST'])
@ui_login_required
def ui_key_delete(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        flash('Key not found.', 'error')
        return redirect(url_for('ui_keys'))

    IPWhitelist.delete().where(IPWhitelist.api_key_id == key.id).execute()
    key.delete_instance()
    flash('Key deleted.', 'success')
    return redirect(url_for('ui_keys'))


@app.route('/keys/<uid>/whitelist/add', methods=['POST'])
@ui_login_required
def ui_whitelist_add(uid):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        flash('Key not found.', 'error')
        return redirect(url_for('ui_keys'))

    ip = request.form.get('src_ip_address', '').strip()
    if ip:
        IPWhitelist.create(api_key_id=key.id, src_ip_address=ip)
        flash(f'{ip} added to whitelist.', 'success')
    return redirect(url_for('ui_key_detail', uid=uid))


@app.route('/keys/<uid>/whitelist/<int:wl_id>/delete', methods=['POST'])
@ui_login_required
def ui_whitelist_delete(uid, wl_id):
    try:
        key = APIKey.get(APIKey.uid == uid)
    except APIKey.DoesNotExist:
        flash('Key not found.', 'error')
        return redirect(url_for('ui_keys'))

    try:
        entry = IPWhitelist.get(
            (IPWhitelist.id == wl_id) & (IPWhitelist.api_key_id == key.id))
        entry.delete_instance()
        flash('IP removed.', 'success')
    except IPWhitelist.DoesNotExist:
        flash('Entry not found.', 'error')
    return redirect(url_for('ui_key_detail', uid=uid))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_permissions_form():
    raw = request.form.get('permissions_json', '{}')
    try:
        perms = json.loads(raw)
        if isinstance(perms, dict):
            return perms
    except (ValueError, TypeError):
        pass
    return {}


def _parse_ts_expires():
    val = request.form.get('ts_expires', '').strip()
    if not val:
        return None
    try:
        return datetime.strptime(val, '%Y-%m-%dT%H:%M')
    except ValueError:
        return None
