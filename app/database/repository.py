"""
Database Repository Module (prd.md Section 24, 25, 29)
Provides clean data access patterns for storing and querying traffic samples.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import sqlite3

from app.database.database import get_db_connection
from app.database.models import TrafficSampleCreate, TrafficSampleRead, TrafficPoint
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
