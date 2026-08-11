from cryptography.fernet import Fernet

from app.infra.settings import credential_settings


def encrypt_api_key(plaintext: str) -> str:
    """AES-GCM via Fernet, never stored or logged in plaintext
    (step5_trust_boundary.md Part D §4). Decrypted only in-memory, at task
    time, never persisted."""
    return Fernet(credential_settings.encryption_key).encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    return Fernet(credential_settings.encryption_key).decrypt(ciphertext.encode()).decode()
