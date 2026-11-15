"""Corte ultra-permanente del ejercicio vigente.

Solo cuentan los clientes asignados (campo ``asignado_at``) a partir del
31 oct 2026, inicio de la publicación del reel 19 alquileres.

Los clientes propios del asesor (tabla ``asesor_clientes``) cuentan si
``created_at`` es el 31 oct 2026 o después.

Los anteriores se conservan en los datos (historia e identificación de
quienes regresan) pero no se muestran ni se cuentan en paneles, listas,
alertas, tableros ni reportes del ejercicio nuevo.

Sin fecha parseable → se ocultan (se tratan como anteriores al corte).
La fecha se toma en America/Caracas cuando el valor trae zona horaria.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

CARACAS = ZoneInfo('America/Caracas')
CORTE_FECHA = date(2026, 10, 31)
CORTE_ISO = '2026-10-31'
CORTE_LABEL = '31 oct 2026'
CORTE_MOTIVO = 'inicio de la publicación del reel 19 alquileres'
CORTE_NOTA = (
    f'Solo se muestran clientes asignados desde el {CORTE_LABEL} '
    f'({CORTE_MOTIVO}). Los anteriores se conservan en el registro, '
    f'pero no aparecen aquí.'
)


def fecha_de(iso):
    """Devuelve la fecha calendario en America/Caracas, o None si no se puede leer."""
    if iso is None:
        return None
    s = str(iso).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CARACAS)
        return dt.astimezone(CARACAS).date()
    except Exception:
        pass
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def en_ejercicio(*, asignado_at=None, created_at=None, propio=False) -> bool:
    """True si el cliente entra en el ejercicio vigente.

    Asignados: usa ``asignado_at``.
    Propios del asesor (propio=True): usa ``created_at``.
    Sin fecha o fecha anterior al 31 oct 2026 → False.
    """
    raw = created_at if propio else asignado_at
    d = fecha_de(raw)
    if d is None:
        return False
    return d >= CORTE_FECHA


def filtrar(items, *, propio=False, asignado_field='asignado_at', creado_field='created_at'):
    """Filtra una lista de dicts. No muta ni borra la fuente."""
    out = []
    for x in items or []:
        if not isinstance(x, dict):
            continue
        if propio:
            ok = en_ejercicio(created_at=x.get(creado_field), propio=True)
        else:
            ok = en_ejercicio(asignado_at=x.get(asignado_field))
        if ok:
            out.append(x)
    return out


def clasificar(items, *, propio=False, asignado_field='asignado_at', creado_field='created_at'):
    """Separa visibles / ocultos y cuenta cuántos no tenían fecha."""
    visibles, ocultos, sin_fecha = [], [], 0
    for x in items or []:
        if not isinstance(x, dict):
            continue
        raw = x.get(creado_field) if propio else x.get(asignado_field)
        if fecha_de(raw) is None:
            sin_fecha += 1
            ocultos.append(x)
            continue
        if en_ejercicio(asignado_at=None if propio else raw, created_at=raw if propio else None, propio=propio):
            visibles.append(x)
        else:
            ocultos.append(x)
    return {'visibles': visibles, 'ocultos': ocultos, 'sin_fecha': sin_fecha}
