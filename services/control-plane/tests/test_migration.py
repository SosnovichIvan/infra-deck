from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from infradeck.db import Database
from infradeck.migrate import migrate


def test_empty_populated_repeat_constraints_and_schema(db):
    schema='infradeck_migration_'+uuid4().hex
    with db.transaction() as tx:
        tx.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    class IsolatedDatabase(Database):
        @contextmanager
        def transaction(self):
            with super().transaction() as tx:
                tx.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
                yield tx
    isolated=IsolatedDatabase(db.url)
    directory=Path(__file__).resolve().parents[1]/'src/infradeck/migrations'
    try:
        migrate(isolated,directory)
        owner,other,project=uuid4(),uuid4(),uuid4()
        with isolated.transaction() as tx:
            tx.execute('INSERT INTO users VALUES (%s,%s,%s,NULL,1)',(owner,'owner','synthetic-hash'))
            tx.execute('INSERT INTO users VALUES (%s,%s,%s,NULL,1)',(other,'other','synthetic-hash'))
            tx.execute('INSERT INTO projects VALUES (%s,%s,%s,%s)',(project,owner,'Project',''))
        migrate(isolated,directory)
        with isolated.transaction() as tx:
            assert tx.execute('SELECT count(*) AS n FROM users').fetchone()['n']==2
            tables={row['table_name'] for row in tx.execute(
                'SELECT table_name FROM information_schema.tables WHERE table_schema=%s',(schema,))}
            assert tables=={'schema_versions','users','sessions','recovery_codes','telegram_updates',
                'rate_limits','projects','servers','connection_checks','encryption_nonces'}
            columns={row['column_name'] for row in tx.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name='servers'",(schema,))}
            assert columns=={'id','project_id','owner_id','name','kind','host','port','username',
                'method','fingerprint','checked_at','encrypted','aad'}
        with pytest.raises(psycopg.errors.UniqueViolation),isolated.transaction() as tx:
            tx.execute('INSERT INTO users VALUES (%s,%s,%s,NULL,1)',(uuid4(),'owner','hash'))
        with pytest.raises(psycopg.errors.CheckViolation),isolated.transaction() as tx:
            tx.execute('INSERT INTO projects VALUES (%s,%s,%s,%s)',(uuid4(),owner,'   ',''))
        with pytest.raises(psycopg.errors.ForeignKeyViolation),isolated.transaction() as tx:
            tx.execute("""INSERT INTO servers VALUES (%s,%s,%s,'Node','VM','example.com',22,
                'deploy','password','SHA256:test',1,'{}','aad')""",(uuid4(),project,other))
    finally:
        with db.transaction() as tx:
            tx.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
