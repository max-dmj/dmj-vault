import json
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as PydanticBaseModel

from dmj_vault.dbaccess import APIKey, IPWhitelist, db

app = FastAPI(title='dmj-vault-api')


@app.on_event('startup')
def startup():
    if db.is_closed():
        db.connect()


@app.on_event('shutdown')
def shutdown():
    if not db.is_closed():
        db.close()


class CheckRequest(PydanticBaseModel):
    api_key: str
    scope: str
    access_type: Literal['read', 'write']
    client_ip: str


@app.post('/check')
def check(body: CheckRequest):
    try:
        key = APIKey.get(APIKey.uid == body.api_key)
    except APIKey.DoesNotExist:
        raise HTTPException(status_code=404, detail='API key not found')

    now = datetime.now()
    if not key.is_valid:
        raise HTTPException(status_code=403, detail='API key is not valid')
    if key.ts_expires is not None and key.ts_expires <= now:
        raise HTTPException(status_code=403, detail='API key has expired')

    whitelist_entries = list(IPWhitelist.select().where(IPWhitelist.api_key_id == key.id))
    if whitelist_entries:
        client_ip = body.client_ip
        allowed_ips = {w.src_ip_address for w in whitelist_entries}
        if client_ip not in allowed_ips:
            raise HTTPException(status_code=403, detail='IP not in whitelist')

    try:
        permissions = json.loads(key.permissions)
    except (ValueError, TypeError):
        permissions = {}

    if body.scope not in permissions:
        raise HTTPException(status_code=403, detail='Scope not permitted')

    granted = permissions[body.scope]
    if body.access_type == 'write' and granted != 'write':
        raise HTTPException(status_code=403, detail='Write access not permitted for scope')

    return {'valid': True}
