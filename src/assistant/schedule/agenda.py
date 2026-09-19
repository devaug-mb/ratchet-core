"""Utilidades de fechas para el horario (sin dependencias del almacén).

Aísla el trato de los días de la semana (con y sin tilde) y el cálculo de la
semana, para que el store, las herramientas y la vista de datos usen lo mismo.
"""

from __future__ import annotations

from datetime import date, timedelta

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Acepta los nombres con y sin tilde y devuelve la forma canónica (con tilde).
_CANONICAL = {
    "lunes": "lunes",
    "martes": "martes",
    "miércoles": "miércoles",
    "miercoles": "miércoles",
    "jueves": "jueves",
    "viernes": "viernes",
    "sábado": "sábado",
    "sabado": "sábado",
    "domingo": "domingo",
}


def weekday_name(day: date) -> str:
    """Nombre del día de la semana de una fecha (lunes..domingo)."""
    return WEEKDAYS[day.weekday()]


def normalize_weekday(name: str) -> str:
    """Devuelve la forma canónica del día ('miercoles' -> 'miércoles')."""
    return _CANONICAL.get(name.strip().lower(), name.strip().lower())


def day_order(name: str) -> int:
    """Orden del día (lunes=0..domingo=6); desconocido va al final."""
    canonical = normalize_weekday(name)
    return WEEKDAYS.index(canonical) if canonical in WEEKDAYS else 99


def week_dates(reference: date) -> list[date]:
    """Las 7 fechas (lunes a domingo) de la semana que contiene `reference`."""
    monday = reference - timedelta(days=reference.weekday())
    return [monday + timedelta(days=index) for index in range(7)]
