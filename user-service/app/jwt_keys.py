"""Genera el par RSA del IdP: `uv run python -m app.jwt_keys` desde user-service/.

La privada se deja con permisos 0600 y no se versiona. Si ya existe, no se
sobrescribe: regenerarla invalida todos los JWT vivos.
"""

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app import config
from app.jwt_issuer import kid_for


def main() -> None:
    private_path = Path(config.JWT_PRIVATE_KEY_PATH)
    public_path = Path(config.JWT_PUBLIC_KEY_PATH)
    if private_path.exists() or public_path.exists():
        raise SystemExit(
            f"Ya existe un par en {private_path} / {public_path}. "
            "Bórralo solo si quieres invalidar todos los JWT emitidos."
        )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    """
    
      encoding=serialization.Encoding.PEM: Define cómo se codificarán los bytes. PEM es el formato más común basado en texto (Base64), fácil de leer o copiar y pegar, que empieza con -----BEGIN PRIVATE KEY----- y termina con -----END PRIVATE KEY-----.
      format=serialization.PrivateFormat.PKCS8: Define la estructura interna estándar de la clave. PKCS#8 es el estándar moderno e independiente del algoritmo para almacenar claves privadas.
      encryption_algorithm=serialization.NoEncryption(): Indica si la clave debe protegerse con una contraseña antes de guardarse. Al usar NoEncryption(), la clave se guarda en texto plano (sin cifrar), por lo que cualquiera que lea el archivo podrá usarla. (Para protegerla con contraseña se usaría BestAvailableEncryption(b"tu_contraseña")).
    """
    private_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    os.chmod(private_path, 0o600)
    public_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"Par RSA generado. kid={kid_for(key.public_key())}")
    print(f"Privada: {private_path} (0600) · Pública: {public_path}")


if __name__ == "__main__":
    main()
