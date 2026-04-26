from peewee import (
    MySQLDatabase, Model,
    AutoField, CharField, TextField, BooleanField,
    DateTimeField, IntegerField,
)
from playhouse.shortcuts import ReconnectMixin


class _ReconnectMySQLDatabase(ReconnectMixin, MySQLDatabase):
    pass


db = _ReconnectMySQLDatabase('DMJ_VAULT', user='vault_admin', host='127.0.0.1', password='')


class BaseModel(Model):
    class Meta:
        database = db


class APIKey(BaseModel):
    id = AutoField()
    uid = CharField(max_length=128, unique=True)
    permissions = TextField()
    is_valid = BooleanField(default=False)
    ts_created = DateTimeField()
    ts_expires = DateTimeField(null=True)

    class Meta:
        table_name = 'API_KEY'


class IPWhitelist(BaseModel):
    id = AutoField()
    api_key_id = IntegerField()
    src_ip_address = CharField(max_length=45)

    class Meta:
        table_name = 'IP_WHITELIST'


class Admin(BaseModel):
    id = AutoField()
    login = CharField(max_length=128)
    password = CharField(max_length=255, default='*')

    class Meta:
        table_name = 'ADMIN'
