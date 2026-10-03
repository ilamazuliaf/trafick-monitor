"""
SNMP Parser and Optical Power Converter Module (PRD Section 8.4 & 10)
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from app.olt.config import OLTConfig
from app.olt.models import ONT


SENTINEL_VALUES = {-2147483648, 65535, 2147483647, -999}


def clean_string_val(val: Any) -> str:
    """
    Cleans string prefixes such as STRING:, Hex-STRING:, INTEGER:, quotes, etc.
    """
    if val is None:
        return ""
    s = str(val).strip()

    # Remove common prefixes
    for prefix in ("STRING:", "Hex-STRING:", "INTEGER:", "Gauge32:", "Counter32:", "Oid:"):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
            break

    # Strip enclosing quotes if any
    if len(s) >= 2 and ((s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))):
        s = s[1:-1].strip()

    return s


def extract_oid_suffix(full_oid: str, root_oid: str) -> str:
    """
    Extracts the suffix from a full OID by stripping root_oid.
    """
    f_norm = full_oid.lstrip(".")
    r_norm = root_oid.lstrip(".")

    if f_norm.startswith(r_norm):
        suffix = f_norm[len(r_norm):].lstrip(".")
        return suffix
    return f_norm


def get_base_suffix(suffix: str) -> str:
    """
    Strips DDM trailing suffixes like .0.0 or .0 from OID suffix.
    """
    cleaned = suffix.strip(".")
    if cleaned.endswith(".0.0"):
        return cleaned[:-4]
    if cleaned.endswith(".0"):
        return cleaned[:-2]
    return cleaned


def parse_pon_and_ont_id(suffix: str) -> Tuple[str, str, str]:
    """
    Parses OID suffix to (slot, pon, ont_id).
    Supports HSGQ 32-bit packed index (PRD Section 10).
    """
    base_s = get_base_suffix(suffix)

    # Check if base_s is a pure integer (e.g. 16777473)
    if base_s.isdigit():
        idx = int(base_s)
        if idx > 65535:
            # Packed 32-bit integer: (Slot << 24) | (Reserved << 16) | (PON << 8) | ONT_ID
            slot_num = (idx >> 24) & 0xFF
            pon_num = (idx >> 8) & 0xFF
            ont_id_num = idx & 0xFF

            slot_str = str(slot_num) if slot_num > 0 else "1"
            pon_str = f"1/1/{pon_num}" if slot_num == 1 or slot_num == 0 else f"{slot_str}/1/{pon_num}"
            ont_id_str = str(ont_id_num)
            return slot_str, pon_str, ont_id_str

    # Dotted suffix e.g. "1.1.38" or "1.38" or "38"
    parts = [p for p in base_s.split(".") if p]
    if len(parts) >= 3:
        slot_str = parts[0]
        pon_str = f"{parts[0]}/{parts[1]}"
        ont_id_str = parts[2]
        return slot_str, pon_str, ont_id_str
    elif len(parts) == 2:
        slot_str = "1"
        pon_str = f"1/1/{parts[0]}"
        ont_id_str = parts[1]
        return slot_str, pon_str, ont_id_str
    elif len(parts) == 1:
        slot_str = "1"
        pon_str = "1/1/1"
        ont_id_str = parts[0]
        return slot_str, pon_str, ont_id_str

    return "1", "1/1/1", suffix


def parse_optical_power(val_str: Any, scale: float = 100.0) -> Optional[float]:
    """
    Converts raw SNMP optical power value to dBm float.
    (PRD Section 8.4 & 10)
    """
    cleaned = clean_string_val(val_str)
    if not cleaned or cleaned.upper() == "N/A":
        return None

    try:
        val_int = int(cleaned)
        if val_int in SENTINEL_VALUES:
            return None
        val_float = float(val_int)
    except ValueError:
        try:
            val_float = float(cleaned)
        except ValueError:
            return None

    if int(val_float) in SENTINEL_VALUES:
        return None

    divider = scale if scale != 0 else 1.0
    return round(val_float / divider, 2)


def map_status(val_str: Any, online_vals: List[str], offline_vals: List[str]) -> str:
    """
    Maps SNMP status value to 'online' or 'offline'.
    """
    cleaned = clean_string_val(val_str)
    online_set = {str(v).strip() for v in online_vals}
    offline_set = {str(v).strip() for v in offline_vals}

    if cleaned in online_set:
        return "online"
    if cleaned in offline_set:
        return "offline"
    return "offline"


def parse_ont_table(
    status_map: Dict[str, str],
    rx_power_map: Optional[Dict[str, str]] = None,
    tx_power_map: Optional[Dict[str, str]] = None,
    vendor_map: Optional[Dict[str, str]] = None,
    model_map: Optional[Dict[str, str]] = None,
    serial_map: Optional[Dict[str, str]] = None,
    name_map: Optional[Dict[str, str]] = None,
    config: Optional[OLTConfig] = None,
) -> List[ONT]:
    """
    Parses WALK results into a list of ONT domain models.
    (PRD Section 8.4)
    """
    if config is None:
        config = OLTConfig()

    rx_map = rx_power_map or {}
    tx_map = tx_power_map or {}
    v_map = vendor_map or {}
    m_map = model_map or {}
    s_map = serial_map or {}
    n_map = name_map or {}

    # Build lookup dictionaries by base_suffix
    def build_suffix_dict(raw_dict: Dict[str, str], root_oid: str) -> Dict[str, str]:
        res = {}
        if not root_oid:
            return res
        for full_oid, val in raw_dict.items():
            suf = extract_oid_suffix(full_oid, root_oid)
            base_s = get_base_suffix(suf)
            res[base_s] = val
        return res

    rx_by_base = build_suffix_dict(rx_map, config.oid_ont_rx_power)
    tx_by_base = build_suffix_dict(tx_map, config.oid_ont_tx_power)
    v_by_base = build_suffix_dict(v_map, config.oid_ont_vendor)
    m_by_base = build_suffix_dict(m_map, config.oid_ont_model)
    s_by_base = build_suffix_dict(s_map, config.oid_ont_serial)
    n_by_base = build_suffix_dict(n_map, config.oid_ont_name)

    ont_list: List[ONT] = []

    for full_oid, raw_status in status_map.items():
        suffix = extract_oid_suffix(full_oid, config.oid_ont_status)
        base_s = get_base_suffix(suffix)

        slot, pon, ont_id = parse_pon_and_ont_id(suffix)
        status = map_status(raw_status, config.ont_status_online_values, config.ont_status_offline_values)

        rx_power = parse_optical_power(rx_by_base.get(base_s), config.rx_power_scale)
        tx_power = parse_optical_power(tx_by_base.get(base_s), config.rx_power_scale)
        vendor = clean_string_val(v_by_base.get(base_s, ""))
        model = clean_string_val(m_by_base.get(base_s, ""))
        serial = clean_string_val(s_by_base.get(base_s, ""))
        name = clean_string_val(n_by_base.get(base_s, ""))

        ont = ONT(
            olt=config.olt_name,
            slot=slot,
            pon=pon,
            ont_id=ont_id,
            serial_number=serial,
            vendor=vendor,
            model=model,
            name=name,
            status=status,
            rx_power=rx_power,
            tx_power=tx_power,
        )
        ont_list.append(ont)

    return ont_list
