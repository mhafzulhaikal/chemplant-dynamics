from __future__ import annotations

_TIME_UNIT_ALIASES = {
    's': 'seconds',
    'sec': 'seconds',
    'secs': 'seconds',
    'second': 'seconds',
    'seconds': 'seconds',
    'm': 'minutes',
    'min': 'minutes',
    'mins': 'minutes',
    'minute': 'minutes',
    'minutes': 'minutes',
    'h': 'hours',
    'hr': 'hours',
    'hrs': 'hours',
    'hour': 'hours',
    'hours': 'hours',
}


def normalize_time_unit(time_unit: str | None) -> str:
    unit = str(time_unit or 'minutes').strip().lower()
    normalized = _TIME_UNIT_ALIASES.get(unit)
    if normalized is None:
        raise ValueError(f'Unsupported time_unit: {time_unit!r}. Use seconds, minutes, or hours.')
    return normalized


def minutes_per_time_unit(time_unit: str | None = None) -> float:
    unit = normalize_time_unit(time_unit)
    if unit == 'seconds':
        return 1.0 / 60.0
    if unit == 'minutes':
        return 1.0
    if unit == 'hours':
        return 60.0
    raise ValueError(f'Unsupported normalized time unit: {unit!r}')


def to_minutes(value: float, time_unit: str | None = None) -> float:
    return float(value) * minutes_per_time_unit(time_unit)


def from_minutes(value: float, time_unit: str | None = None) -> float:
    return float(value) / minutes_per_time_unit(time_unit)


def time_unit_short_label(time_unit: str | None = None) -> str:
    unit = normalize_time_unit(time_unit)
    return {
        'seconds': 'sec',
        'minutes': 'min',
        'hours': 'hr',
    }[unit]
