"""Generate local-only key files; never overwrite existing keys."""
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

root = Path('.runtime')
root.mkdir(mode=0o700, exist_ok=True)
for name in ('kek', 'otp'):
    path = root / name
    if not path.exists():
        with path.open('xb') as stream:
            os.chmod(path, 0o600)
            stream.write(os.urandom(32))
path = root / 'rsa.pem'
if not path.exists():
    with path.open('xb') as stream:
        os.chmod(path, 0o600)
        stream.write(rsa.generate_private_key(public_exponent=65537, key_size=3072).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
