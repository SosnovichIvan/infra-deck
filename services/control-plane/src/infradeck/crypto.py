"""Standard JWE in transit; versioned AEAD envelope at rest."""

import base64
import hashlib
import hmac
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jwcrypto import jwe, jwk

from infradeck.errors import Rejected


def digest(key: bytes, value: str) -> str:
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode()


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value)


class Vault:
    def __init__(self, kek: bytes, private_key: bytes, otp_key: bytes):
        if len(kek) != 32 or len(otp_key) < 32:
            raise ValueError("Invalid encryption key material")
        self.kek, self.otp_key = kek, otp_key
        self.rsa = jwk.JWK.from_pem(private_key)
        self.kid = self.rsa.thumbprint()

    def public_key(self) -> dict[str, str]:
        return {
            **json.loads(self.rsa.export_public()),
            "kid": self.kid,
            "alg": "RSA-OAEP-256",
            "use": "enc",
        }

    def unwrap(self, compact: str) -> dict[str, Any]:
        try:
            message = jwe.JWE(algs=["RSA-OAEP-256", "A256GCM"])
            message.deserialize(compact, key=self.rsa)
            if message.jose_header.get("kid") != self.kid:
                raise ValueError("Unknown key")
            payload = json.loads(message.payload)
            if not isinstance(payload, dict):
                raise ValueError("Invalid envelope")
            return payload
        except (jwe.InvalidJWEData, ValueError, KeyError, TypeError):
            raise Rejected("Не удалось расшифровать данные подключения") from None

    def seal(self, data: str, aad: str) -> dict[str, str]:
        dek, nonce, wrap_nonce = os.urandom(32), os.urandom(12), os.urandom(12)
        return {
            "version": "1",
            "nonce": encode(nonce),
            "wrap_nonce": encode(wrap_nonce),
            "key": encode(AESGCM(self.kek).encrypt(wrap_nonce, dek, aad.encode())),
            "data": encode(AESGCM(dek).encrypt(nonce, data.encode(), aad.encode())),
        }

    def open(self, envelope: dict[str, str], aad: str) -> str:
        if envelope["version"] != "1":
            raise Rejected("Неизвестная версия ключа", 503)
        dek = AESGCM(self.kek).decrypt(
            decode(envelope["wrap_nonce"]), decode(envelope["key"]), aad.encode()
        )
        return (
            AESGCM(dek)
            .decrypt(decode(envelope["nonce"]), decode(envelope["data"]), aad.encode())
            .decode()
        )
