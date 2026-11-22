import os


# sqlite de este servicio; en tests, DATABASE_URL=sqlite:///:memory:
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.sqlite")

# Dónde vive el IdP y su timeout lo lee el paquete
# microservices-user-service-client del entorno (USER_SERVICE_URL,
# HTTP_TIMEOUT_SECONDS).
