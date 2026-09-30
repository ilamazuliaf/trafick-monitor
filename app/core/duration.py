"""
Generic Duration Parsing Module (prd.md Section 10, 11, 13, 14)
Handles conversions between duration strings (e.g. 5m, 1h, 2d) and seconds,
as well as dynamic label formatting for the UI.
"""
import re

DURATION_PATTERN = re.compile(r"^\s*(\d+)\s*([mhd])\s*$", re.IGNORECASE)

UNIT_SECONDS = {
    "m": 60,
    "h": 3600,
    "d": 86400
}

UNIT_LABELS = {
    "m": "Menit",
    "h": "Jam",
    "d": "Hari"
}


def parse_duration_seconds(duration_str: str) -> int:
    """
    Parses duration string like '5m', '1h', '2d' into total seconds.
    Raises ValueError for invalid duration format.
    """
    if not isinstance(duration_str, str):
        raise ValueError(f"Duration must be a string, got {type(duration_str).__name__}")
    
    match = DURATION_PATTERN.match(duration_str)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration_str}'. "
            "Must be number followed by unit 'm' (minutes), 'h' (hours), or 'd' (days). E.g., '5m', '1h', '2d'."
        )
    
    value_str, unit = match.groups()
    value = int(value_str)
    unit = unit.lower()
    
    if value <= 0:
        raise ValueError(f"Duration value must be greater than zero, got {value}")
        
    return value * UNIT_SECONDS[unit]


def format_duration_label(duration_str: str) -> str:
    """
    Generically formats a duration string into a human-readable Indonesian label.
    e.g. '5m' -> '5 Menit', '1h' -> '1 Jam', '2d' -> '2 Hari'
    """
    match = DURATION_PATTERN.match(duration_str)
    if not match:
        raise ValueError(f"Cannot format invalid duration: '{duration_str}'")
    
    value_str, unit = match.groups()
    value = int(value_str)
    unit = unit.lower()
    
    return f"{value} {UNIT_LABELS[unit]}"
