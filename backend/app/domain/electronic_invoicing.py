"""Facturación electrónica — DESACTIVADA por diseño (docs/05 §10, 12 §4).

No se activa ni se simula: el proveedor por defecto FALLA SIEMPRE con
un mensaje que explica cómo habilitarlo. Activarla exige un Proveedor
Tecnológico autorizado y es una decisión de negocio y legal.
"""
from __future__ import annotations


class InvoiceProvider:
    def issue(self, receipt_id: int, payload: dict) -> dict:
        raise NotImplementedError

    def status(self, external_id: str) -> dict:
        raise NotImplementedError


class DisabledProvider(InvoiceProvider):
    codigo = "DISABLED"

    def issue(self, receipt_id: int, payload: dict) -> dict:
        raise RuntimeError(
            "La facturación electrónica está DESACTIVADA "
            f"(PARKIUM_PROVEEDOR_FACTURACION={self.codigo}). "
            "Activar exige un Proveedor Tecnológico autorizado: es una decisión "
            "de negocio y de cumplimiento legal (docs/12-preguntas-abiertas.md §4). "
            "El comprobante emitido es un documento interno.")

    def status(self, external_id: str) -> dict:
        raise RuntimeError("Facturación electrónica desactivada: no hay estado que consultar.")


def get_provider() -> InvoiceProvider:
    return DisabledProvider()
