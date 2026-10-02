"""
Database Repository Module (prd.md Section 24, 25, 29)
Provides clean data access patterns for storing and querying traffic samples.
"""
import os
import shutil
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from app.database.database import get_db_connection
from app.database.models import (
    TrafficSampleCreate, TrafficSampleRead, TrafficPoint,
    CustomerCreate, CustomerUpdate, CustomerRead
)
from app.core.config import settings
from app.core.logging import logger


class TrafficRepository:

    @staticmethod
    def insert_sample(sample: TrafficSampleCreate) -> None:
        """
        Inserts a single traffic sample into SQLite.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO traffic_samples (timestamp, interface_name, rx_bytes, tx_bytes, rx_bps, tx_bps)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    sample.timestamp,
                    sample.interface_name,
                    sample.rx_bytes,
                    sample.tx_bytes,
                    sample.rx_bps,
                    sample.tx_bps
                )
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error inserting traffic sample for {sample.interface_name}: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_latest_sample(interface_name: str) -> Optional[TrafficSampleRead]:
        """
        Retrieves the most recent sample for a given interface.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, interface_name, rx_bytes, tx_bytes, rx_bps, tx_bps
                FROM traffic_samples
                WHERE interface_name = ?
                ORDER BY timestamp DESC
                LIMIT 1;
                """,
                (interface_name,)
            )
            row = cursor.fetchone()
            if row:
                return TrafficSampleRead(**dict(row))
            return None
        finally:
            conn.close()

    @staticmethod
    def get_traffic_points(
        interface_name: str,
        start_iso: str,
        end_iso: str,
        max_points: int = 500
    ) -> List[TrafficPoint]:
        """
        Queries traffic points within a time window [start_iso, end_iso].
        Supports 'all' to return total aggregated traffic across all interfaces.
        Downsamples results if point count exceeds max_points (prd.md Section 29).
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if interface_name.lower() == "all":
                cursor.execute(
                    """
                    SELECT timestamp, SUM(rx_bps) as rx_bps, SUM(tx_bps) as tx_bps
                    FROM traffic_samples
                    WHERE timestamp >= ? AND timestamp <= ?
                    GROUP BY timestamp
                    ORDER BY timestamp ASC;
                    """,
                    (start_iso, end_iso)
                )
            else:
                cursor.execute(
                    """
                    SELECT timestamp, rx_bps, tx_bps
                    FROM traffic_samples
                    WHERE interface_name = ? AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp ASC;
                    """,
                    (interface_name, start_iso, end_iso)
                )
            rows = cursor.fetchall()
            if not rows:
                return []

            points = [
                TrafficPoint(
                    timestamp=row["timestamp"],
                    rx_bps=round(float(row["rx_bps"] or 0), 2),
                    tx_bps=round(float(row["tx_bps"] or 0), 2)
                )
                for row in rows
            ]

            # Perform downsampling if points exceed max_points (prd.md Section 29)
            if len(points) <= max_points:
                return points

            return TrafficRepository._downsample(points, max_points)
        finally:
            conn.close()

    @staticmethod
    def get_traffic_points_by_interface(
        interface_names: List[str],
        start_iso: str,
        end_iso: str,
        max_points: int = 500
    ) -> dict:
        """
        Queries traffic points per interface within a time window [start_iso, end_iso].
        Returns a dictionary mapping interface_name -> List[TrafficPoint].
        """
        result = {}
        for iface_name in interface_names:
            points = TrafficRepository.get_traffic_points(
                interface_name=iface_name,
                start_iso=start_iso,
                end_iso=end_iso,
                max_points=max_points
            )
            result[iface_name] = points
        return result


    @staticmethod
    def _downsample(points: List[TrafficPoint], max_points: int) -> List[TrafficPoint]:
        """
        Averages bucketed points to ensure length <= max_points.
        """
        total_points = len(points)
        bucket_size = total_points / max_points
        downsampled: List[TrafficPoint] = []

        for i in range(max_points):
            start_idx = int(i * bucket_size)
            end_idx = int((i + 1) * bucket_size)
            if start_idx >= total_points:
                break
            bucket = points[start_idx:end_idx]
            if not bucket:
                continue

            avg_rx = sum(p.rx_bps for p in bucket) / len(bucket)
            avg_tx = sum(p.tx_bps for p in bucket) / len(bucket)
            # Use mid-point timestamp for bucket
            mid_ts = bucket[len(bucket) // 2].timestamp

            downsampled.append(
                TrafficPoint(
                    timestamp=mid_ts,
                    rx_bps=round(avg_rx, 2),
                    tx_bps=round(avg_tx, 2)
                )
            )

        return downsampled

    @staticmethod
    def purge_old_samples(retention_seconds: int) -> int:
        """
        Deletes samples older than retention_seconds (prd.md Section 25).
        Returns number of deleted rows.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=retention_seconds)).isoformat()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM traffic_samples WHERE timestamp < ?;",
                (cutoff,)
            )
            deleted_count = cursor.rowcount
            conn.commit()
            if deleted_count > 0:
                logger.info(f"Purged {deleted_count} old traffic samples prior to {cutoff}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error purging old data: {e}")
            return 0
        finally:
            conn.close()


def backup_database() -> str:
    """
    Creates a backup copy of the SQLite database in data/backups/ (tambah_fitur.md Section 44).
    Returns path of created backup file.
    """
    db_path = settings.database_path
    if not os.path.exists(db_path):
        logger.warning(f"Database file does not exist yet at {db_path}, skipping backup.")
        return ""
    
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"traffic_{now_str}.db")
    shutil.copy2(db_path, backup_file)
    logger.info(f"Database backed up to: {backup_file}")
    return backup_file


class CustomerRepository:

    @staticmethod
    def create_customer(customer: CustomerCreate, conn: Optional[sqlite3.Connection] = None) -> CustomerRead:
        close_conn = False
        if conn is None:
            conn = get_db_connection()
            close_conn = True
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor = conn.cursor()
            code = customer.customer_code.strip() if customer.customer_code else None
            user = customer.username.strip()
            name = customer.customer_name.strip()
            phone = customer.phone.strip() if customer.phone else None
            address = customer.address.strip() if customer.address else None
            package = customer.package.strip() if customer.package else None
            notes = customer.notes.strip() if customer.notes else None
            monitored = 1 if customer.monitoring_enabled else 0

            cursor.execute(
                """
                INSERT INTO customers (
                    customer_code, username, customer_name, phone, address, package, monitoring_enabled, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (code, user, name, phone, address, package, monitored, notes, now_iso, now_iso)
            )
            customer_id = cursor.lastrowid
            if close_conn:
                conn.commit()

            return CustomerRead(
                id=customer_id,
                customer_code=code,
                username=user,
                customer_name=name,
                phone=phone,
                address=address,
                package=package,
                monitoring_enabled=bool(monitored),
                notes=notes,
                created_at=now_iso,
                updated_at=now_iso
            )
        finally:
            if close_conn:
                conn.close()

    @staticmethod
    def get_customer_by_username(username: str, conn: Optional[sqlite3.Connection] = None) -> Optional[CustomerRead]:
        close_conn = False
        if conn is None:
            conn = get_db_connection()
            close_conn = True
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM customers WHERE username = ?;", (username.strip(),))
            row = cursor.fetchone()
            if row:
                return CustomerRead(
                    id=row["id"],
                    customer_code=row["customer_code"],
                    username=row["username"],
                    customer_name=row["customer_name"],
                    phone=row["phone"],
                    address=row["address"],
                    package=row["package"],
                    monitoring_enabled=bool(row["monitoring_enabled"]),
                    notes=row["notes"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
            return None
        finally:
            if close_conn:
                conn.close()

    @staticmethod
    def get_customers() -> List[CustomerRead]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM customers ORDER BY username ASC;")
            rows = cursor.fetchall()
            return [
                CustomerRead(
                    id=row["id"],
                    customer_code=row["customer_code"],
                    username=row["username"],
                    customer_name=row["customer_name"],
                    phone=row["phone"],
                    address=row["address"],
                    package=row["package"],
                    monitoring_enabled=bool(row["monitoring_enabled"]),
                    notes=row["notes"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
                for row in rows
            ]
        finally:
            conn.close()

    @staticmethod
    def get_monitored_customers() -> List[CustomerRead]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM customers WHERE monitoring_enabled = 1 ORDER BY username ASC;")
            rows = cursor.fetchall()
            return [
                CustomerRead(
                    id=row["id"],
                    customer_code=row["customer_code"],
                    username=row["username"],
                    customer_name=row["customer_name"],
                    phone=row["phone"],
                    address=row["address"],
                    package=row["package"],
                    monitoring_enabled=bool(row["monitoring_enabled"]),
                    notes=row["notes"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
                for row in rows
            ]
        finally:
            conn.close()

    @staticmethod
    def update_customer(username: str, customer: CustomerUpdate, conn: Optional[sqlite3.Connection] = None) -> Optional[CustomerRead]:
        close_conn = False
        if conn is None:
            conn = get_db_connection()
            close_conn = True
        try:
            existing = CustomerRepository.get_customer_by_username(username, conn=conn)
            if not existing:
                return None
            
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor = conn.cursor()

            code = customer.customer_code if customer.customer_code is not None else existing.customer_code
            name = customer.customer_name if customer.customer_name is not None else existing.customer_name
            phone = customer.phone if customer.phone is not None else existing.phone
            address = customer.address if customer.address is not None else existing.address
            package = customer.package if customer.package is not None else existing.package
            monitoring = customer.monitoring_enabled if customer.monitoring_enabled is not None else existing.monitoring_enabled
            notes = customer.notes if customer.notes is not None else existing.notes

            cursor.execute(
                """
                UPDATE customers
                SET customer_code = ?, customer_name = ?, phone = ?, address = ?, package = ?, monitoring_enabled = ?, notes = ?, updated_at = ?
                WHERE username = ?;
                """,
                (
                    code.strip() if code else None,
                    name.strip() if name else None,
                    phone.strip() if phone else None,
                    address.strip() if address else None,
                    package.strip() if package else None,
                    1 if monitoring else 0,
                    notes.strip() if notes else None,
                    now_iso,
                    username.strip()
                )
            )
            if close_conn:
                conn.commit()

            return CustomerRepository.get_customer_by_username(username, conn=conn)
        finally:
            if close_conn:
                conn.close()

    @staticmethod
    def upsert_customer(customer: CustomerCreate, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        Upserts customer based on username.
        Returns True if updated, False if created.
        """
        existing = CustomerRepository.get_customer_by_username(customer.username.strip(), conn=conn)
        if existing:
            update_data = CustomerUpdate(
                customer_code=customer.customer_code,
                customer_name=customer.customer_name,
                phone=customer.phone,
                address=customer.address,
                package=customer.package,
                monitoring_enabled=customer.monitoring_enabled,
                notes=customer.notes
            )
            CustomerRepository.update_customer(customer.username.strip(), update_data, conn=conn)
            return True  # Updated
        else:
            CustomerRepository.create_customer(customer, conn=conn)
            return False  # Created

    @staticmethod
    def delete_customer(username: str) -> bool:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM customers WHERE username = ?;", (username.strip(),))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def bulk_upsert_customers(customers: List[CustomerCreate]) -> Tuple[int, int]:
        """
        Executes bulk upsert inside a single transaction (tambah_fitur.md Section 16, 44 & 45).
        Returns (created_count, updated_count).
        Rolls back on error.
        """
        backup_database()
        conn = get_db_connection()
        created_count = 0
        updated_count = 0
        try:
            conn.execute("BEGIN TRANSACTION;")
            for cust in customers:
                is_update = CustomerRepository.upsert_customer(cust, conn=conn)
                if is_update:
                    updated_count += 1
                else:
                    created_count += 1
            conn.commit()
            logger.info(f"Bulk customer import success: {created_count} created, {updated_count} updated.")
            return created_count, updated_count
        except Exception as e:
            conn.rollback()
            logger.error(f"Bulk customer import failed, rolled back: {e}")
            raise e
        finally:
            conn.close()

