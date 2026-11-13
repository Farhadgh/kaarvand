"""Gateway selection (settings driven)."""

from __future__ import annotations

from app.billing.gateway import PaymentGateway
from app.billing.noop import NoopGateway
from app.billing.zarinpal import ZarinpalGateway
from app.core.config import Settings, get_settings
from app.core.errors import ConfigError

GATEWAYS: dict[str, type] = {
    "noop": NoopGateway,
    "zarinpal": ZarinpalGateway,
}


def get_gateway(settings: Settings | None = None) -> PaymentGateway:
    cfg = settings or get_settings()
    factory = GATEWAYS.get(cfg.payment_gateway)
    if factory is None:
        raise ConfigError(
            code="config.unknown_payment_gateway",
            params={"gateway": cfg.payment_gateway},
        )
    if factory is ZarinpalGateway:
        return ZarinpalGateway(cfg)  # type: ignore[return-value]
    return factory()  # type: ignore[return-value]

