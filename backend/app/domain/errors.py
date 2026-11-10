"""Excepciones de dominio que el middleware traduce a los códigos de docs/04 §4.1."""
from __future__ import annotations


class DomainError(Exception):
    codigo = "validacion"
    mensaje = "Regla de negocio incumplida."
    status = 400

    def __init__(self, mensaje: str | None = None, detalle: dict | None = None):
        super().__init__(mensaje or self.mensaje)
        self.mensaje = mensaje or self.mensaje
        self.detalle = detalle or {}


class ClockIntegrityError(DomainError):
    """El reloj no es confiable: bloquea cotización y cobro (docs/04 §4.1)."""
    codigo = "reloj_no_confiable"
    mensaje = "Hora no confiable: el cobro está bloqueado."
    status = 400


class ClockUnverifiableError(DomainError):
    codigo = "reloj_no_verificable"
    mensaje = "La fuente externa no respondió y no hay ancla válida."
    status = 503


class CredentialsError(DomainError):
    codigo = "credenciales"
    mensaje = "Usuario o contraseña incorrectos."
    status = 401


class NotAuthenticatedError(DomainError):
    codigo = "no_autenticado"
    mensaje = "Sesión no válida o expirada."
    status = 401


class AuthorizationError(DomainError):
    codigo = "sin_permisos"
    mensaje = "No tiene permisos para esta operación."
    status = 403


class RestrictedError(DomainError):
    codigo = "recurso_restringido"
    mensaje = "Acceso restringido."
    status = 403


class NotFoundError(DomainError):
    codigo = "no_encontrado"
    mensaje = "No existe el registro solicitado."
    status = 404


class ConflictError(DomainError):
    codigo = "conflicto"
    mensaje = "Conflicto con el estado actual."
    status = 409


class PlanLimitError(DomainError):
    """Cuota del plan excedida: 409 `limite_plan_alcanzado` (docs/04 §4.1)."""
    codigo = "limite_plan_alcanzado"
    mensaje = "El límite del plan fue alcanzado."
    status = 409
    def __init__(self, mensaje: str | None = None, detalle: dict | None = None):
        super().__init__(mensaje or self.mensaje, detalle)


class IdempotencyConflictError(ConflictError):
    codigo = "idempotencia"
    mensaje = "La clave de idempotencia ya fue usada con otro objetivo."
