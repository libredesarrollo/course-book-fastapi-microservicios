import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


# Duración de vida del token opaco (capítulo 1: caducidad, 60 min).
TOKEN_TTL_MINUTES = _int("TOKEN_TTL_MINUTES", 60)
TOKEN_TTL_SECONDS = TOKEN_TTL_MINUTES * 60

# Modo de tokens: "jwt" (stateless, verificación local) u "opaque" (el de siempre).
# TOKEN_MODE = os.environ.get("TOKEN_MODE", "opaque")
TOKEN_MODE = os.environ.get("TOKEN_MODE", "jwt")

# JWT RS256: TTL corto porque sin filas no hay revocación (capítulo 10).
JWT_TTL_MINUTES = _int("JWT_TTL_MINUTES", 15)
JWT_ISSUER = os.environ.get("JWT_ISSUER", "user-service")
JWT_PRIVATE_KEY_PATH = os.environ.get("JWT_PRIVATE_KEY_PATH", "jwt_keys/private.pem")
JWT_PUBLIC_KEY_PATH = os.environ.get("JWT_PUBLIC_KEY_PATH", "jwt_keys/public.pem")

# sqlite de este servicio; en tests, DATABASE_URL=sqlite:///:memory:
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.sqlite")

# Límites de intentos de login sobre POST /api/tokens (recibe contraseñas).
# Dos contadores: por cuenta (martilleo) y por IP (barrido de emails).
LOGIN_THROTTLE_PER_ACCOUNT = _int("LOGIN_THROTTLE_PER_ACCOUNT", 5)
LOGIN_THROTTLE_PER_IP = _int("LOGIN_THROTTLE_PER_IP", 20)
LOGIN_THROTTLE_DECAY_SECONDS = _int("LOGIN_THROTTLE_DECAY_SECONDS", 60)
