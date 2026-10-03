"""
Async SNMP Client Module (PRD Section 8.3)
High-performance implementation using GetBulk for SNMP v2c/v3.
"""
import time
from typing import Dict, Optional, Tuple
from pysnmp.hlapi.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    get_cmd,
    walk_cmd,
    bulk_walk_cmd,
    EndOfMibView,
    NoSuchObject,
    NoSuchInstance,
)

from app.core.logging import logger
from app.olt.config import OLTConfig


class SNMPClient:
    """
    Asynchronous SNMP Client for OLT monitoring using pysnmp.
    Optimized with GetBulk (bulk_walk_cmd) for high performance.
    """

    def __init__(self, config: OLTConfig):
        self.config = config
        self._engine = SnmpEngine()

    def _get_auth_data(self) -> CommunityData:
        mp_model = 1  # SNMP v2c default
        ver = str(self.config.snmp_version).lower()
        if ver in ("1", "v1"):
            mp_model = 0
        elif ver in ("2c", "2", "v2c"):
            mp_model = 1
        return CommunityData(self.config.snmp_community, mpModel=mp_model)

    async def _create_target(self) -> UdpTransportTarget:
        return await UdpTransportTarget.create(
            (self.config.olt_host, self.config.olt_port),
            timeout=self.config.snmp_timeout,
            retries=self.config.snmp_retries,
        )

    async def get(self, oid: str) -> Optional[str]:
        """
        Executes SNMP GET for a single OID.
        (PRD Section 8.3)
        """
        if not oid or not oid.strip():
            return None

        try:
            target = await self._create_target()
            auth = self._get_auth_data()

            error_indication, error_status, error_index, var_binds = await get_cmd(
                self._engine, auth, target, ContextData(), ObjectType(ObjectIdentity(oid))
            )

            if error_indication:
                logger.warning(f"SNMP GET error: {error_indication} for OID {oid}")
                return None
            if error_status:
                logger.warning(f"SNMP GET error status: {error_status.prettyPrint()} at {error_index}")
                return None

            for var_bind in var_binds:
                val = var_bind[1]
                if isinstance(val, (EndOfMibView, NoSuchObject, NoSuchInstance)) or val.__class__.__name__ in ("EndOfMibView", "NoSuchObject", "NoSuchInstance"):
                    return None
                val_str = str(val.prettyPrint() if hasattr(val, "prettyPrint") else val)
                if "nosuchinstance" in val_str.lower() or "nosuchobject" in val_str.lower():
                    return None
                return val_str
            return None
        except Exception as e:
            logger.error(f"Exception during SNMP GET {oid}: {e}", exc_info=True)
            return None

    async def walk(self, oid: str, max_repetitions: int = 25) -> Dict[str, str]:
        """
        Executes SNMP WALK (using GetBulk for v2c/v3) for an OID subtree.
        Returns dict mapping full_oid string -> value string.
        (PRD Section 8.3)
        """
        result: Dict[str, str] = {}
        if not oid or not oid.strip():
            return result

        try:
            target = await self._create_target()
            auth = self._get_auth_data()
            root_norm = oid.strip(".")

            ver = str(self.config.snmp_version).lower()
            use_bulk = ver not in ("1", "v1")

            if use_bulk:
                generator = bulk_walk_cmd(
                    self._engine,
                    auth,
                    target,
                    ContextData(),
                    0,
                    max_repetitions,
                    ObjectType(ObjectIdentity(oid)),
                    lexicographicalMode=False,
                )
            else:
                generator = walk_cmd(
                    self._engine,
                    auth,
                    target,
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                    lexicographicalMode=False,
                )

            async for error_indication, error_status, error_index, var_binds in generator:
                if error_indication:
                    logger.warning(f"SNMP WALK error: {error_indication} for OID {oid}")
                    break
                if error_status:
                    logger.warning(f"SNMP WALK error status: {error_status.prettyPrint()} at {error_index}")
                    break

                for name, val in var_binds:
                    if isinstance(val, (EndOfMibView, NoSuchObject, NoSuchInstance)) or val.__class__.__name__ in ("EndOfMibView", "NoSuchObject", "NoSuchInstance"):
                        break
                    val_str = str(val.prettyPrint() if hasattr(val, "prettyPrint") else val)
                    if "nosuchinstance" in val_str.lower() or "nosuchobject" in val_str.lower():
                        continue
                    name_str = str(name).strip(".")
                    if not name_str.startswith(root_norm):
                        break
                    result[name_str] = val_str

        except Exception as e:
            logger.error(f"Exception during SNMP WALK {oid}: {e}", exc_info=True)

        return result

    async def check_connection(self) -> Tuple[bool, str, float]:
        """
        Checks SNMP connectivity to OLT. Returns (connected, message, latency_ms).
        (PRD Section 8.3)
        """
        test_oid = self.config.oid_ont_status or "1.3.6.1.2.1.1.3.0"
        t0 = time.monotonic()
        try:
            target = await self._create_target()
            auth = self._get_auth_data()

            error_indication, error_status, error_index, var_binds = await get_cmd(
                self._engine, auth, target, ContextData(), ObjectType(ObjectIdentity(test_oid))
            )
            t1 = time.monotonic()
            latency = round((t1 - t0) * 1000, 2)

            if error_indication:
                return False, f"ERROR ({error_indication})", 0.0
            if error_status:
                return False, f"ERROR ({error_status.prettyPrint()})", 0.0

            if var_binds:
                val = var_binds[0][1]
                val_str = str(val).lower()
                if isinstance(val, (NoSuchInstance, NoSuchObject)) or "nosuchinstance" in val_str or "nosuchobject" in val_str:
                    # If test_oid is a table root, try walking 1 item
                    ver = str(self.config.snmp_version).lower()
                    if ver not in ("1", "v1"):
                        gen = bulk_walk_cmd(
                            self._engine,
                            auth,
                            target,
                            ContextData(),
                            0,
                            1,
                            ObjectType(ObjectIdentity(test_oid)),
                            lexicographicalMode=False,
                        )
                    else:
                        gen = walk_cmd(
                            self._engine,
                            auth,
                            target,
                            ContextData(),
                            ObjectType(ObjectIdentity(test_oid)),
                            lexicographicalMode=False,
                        )

                    async for e_ind, e_stat, _, v_binds in gen:
                        if e_ind:
                            return False, f"ERROR ({e_ind})", 0.0
                        if e_stat:
                            return False, f"ERROR ({e_stat.prettyPrint()})", 0.0
                        if v_binds:
                            v_val_obj = v_binds[0][1]
                            v_val = str(v_val_obj).lower()
                            if isinstance(v_val_obj, (NoSuchInstance, NoSuchObject)) or "nosuchinstance" in v_val or "nosuchobject" in v_val:
                                return False, "ERROR (OID tidak ditemukan di OLT)", 0.0
                            return True, "CONNECTED", latency
                        break

            return True, "CONNECTED", latency
        except Exception as e:
            return False, f"ERROR ({str(e)})", 0.0
