"""
ONT Domain Model (PRD Section 8.2)
"""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ONT:
    olt: str
    slot: str
    pon: str
    ont_id: str
    serial_number: str = ""
    vendor: str = ""
    model: str = ""
    name: str = ""
    status: str = ""
    rx_power: Optional[float] = None
    tx_power: Optional[float] = None

    @property
    def display_model(self) -> str:
        """
        Returns combined Vendor + Model, or fallback to serial_number, or '-'.
        (PRD Section 6.2, 8.2 & 16)
        """
        parts = [p for p in [self.vendor, self.model] if p and p.strip()]
        if parts:
            return " ".join(parts)
        if self.serial_number and self.serial_number.strip():
            return self.serial_number.strip()
        return "-"

    @property
    def is_online(self) -> bool:
        return self.status.lower() == "online"

    @property
    def is_offline(self) -> bool:
        return self.status.lower() == "offline"

    def sort_key(self) -> Tuple:
        """
        Natural sort key: OLT > Slot > PON > ONT ID
        """
        try:
            slot_key = int(self.slot)
        except ValueError:
            slot_key = self.slot

        pon_parts = tuple(int(x) if x.isdigit() else x for x in self.pon.split("/"))

        try:
            ont_id_key = int(self.ont_id)
        except ValueError:
            ont_id_key = self.ont_id

        return (self.olt, slot_key, pon_parts, ont_id_key)
