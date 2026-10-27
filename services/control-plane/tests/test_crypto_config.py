import json
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from jwcrypto import jwe
from pydantic import ValidationError

from conftest import envelope
from infradeck.config import Settings
from infradeck.crypto import Vault
from infradeck.errors import Rejected
from infradeck.migrate import migrate


def test_vault(vault,connection):
    sealed=vault.seal('a-private-value','owner:host')
    assert vault.open(sealed,'owner:host')=='a-private-value'
    with pytest.raises(InvalidTag):vault.open(sealed,'other:host')
    with pytest.raises(Rejected):vault.open({**sealed,'version':'100'},'owner:host')
    assert vault.unwrap(envelope(vault,'nonce',connection))['connection']['password']=='ssh-secret-never-return'
    for data in ({'kid':'wrong'},):
        message=jwe.JWE(b'{}',protected={'alg':'RSA-OAEP-256','enc':'A256GCM',**data})
        message.add_recipient(vault.rsa)
        with pytest.raises(Rejected):vault.unwrap(message.serialize(compact=True))
    message=jwe.JWE(b'[]',protected={'alg':'RSA-OAEP-256','enc':'A256GCM','kid':vault.kid})
    message.add_recipient(vault.rsa)
    with pytest.raises(Rejected):vault.unwrap(message.serialize(compact=True))
    with pytest.raises(ValueError):Vault(b'short',b'',b'short')
    assert 'd' not in vault.public_key()


@pytest.mark.parametrize('changes',[
    {'origin':'ftp://example.com'}, {'origin':'http://example.com/path'},
    {'telegram_proxy':'https://proxy:3128'}, {'telegram_proxy':'http://user:secret@proxy:3128'},
    {'telegram_proxy':'http://proxy'}, {'telegram_proxy':'http://proxy:3128/path'},
    {'production':True}, {'telegram_webhook_secret':'short'},
])
def test_config_rejects(settings,changes):
    with pytest.raises(ValidationError):Settings(**{**settings.model_dump(),**changes})


def test_config_production(settings):
    settings=Settings(**{**settings.model_dump(),'origin':'https://infra.example',
        'production':True,'telegram_proxy':'http://telegram-proxy:19840'})
    assert 'TEST_ONLY' not in repr(settings)


def test_migration_preserves_data(db,logged):
    root=Path(__file__).resolve().parents[1]/'src/infradeck/migrations'
    migrate(db,root)
    with db.transaction() as tx:
        assert tx.execute('SELECT count(*) AS n FROM users').fetchone()['n']==1
        assert tx.execute('SELECT count(*) AS n FROM schema_versions').fetchone()['n']==1
