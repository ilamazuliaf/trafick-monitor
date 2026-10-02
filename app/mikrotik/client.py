"""
MikroTik RouterOS API Client Module (prd.md Section 47 & 48)
Handles low-level socket protocol communication with RouterOS API / API-SSL.
"""
import socket
import ssl
import struct
from typing import Dict, List, Any, Optional

from app.core.config import settings
from app.core.logging import logger


class MikrotikAPIError(Exception):
    """Custom exception for MikroTik API errors."""
    pass


class MikrotikClient:
    """
    Native Python RouterOS API protocol implementation.
    Supports standard API (port 8728) and API-SSL (port 8729).
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: Optional[bool] = None,
        verify_ssl: Optional[bool] = None,
        timeout: float = 5.0
    ):
        self.host = host or settings.mikrotik_host
        self.port = port or settings.mikrotik_port
        self.username = username or settings.mikrotik_username
        self.password = password or settings.mikrotik_password
        self.use_ssl = use_ssl if use_ssl is not None else settings.mikrotik_use_ssl
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.mikrotik_verify_ssl
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """
        Establishes socket connection and authenticates with RouterOS.
        Returns True on success, False on connection failure.
        """
        try:
            raw_sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            
            if self.use_ssl:
                context = ssl.create_default_context()
                if not self.verify_ssl:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                self.sock = context.wrap_socket(raw_sock, server_hostname=self.host)
            else:
                self.sock = raw_sock

            # Login flow
            return self._login()
        except Exception as e:
            logger.warning(f"Failed to connect to MikroTik ({self.host}:{self.port}): {e}")
            self.close()
            return False

    def close(self) -> None:
        """Closes socket connection."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _login(self) -> bool:
        """
        Performs RouterOS API post-v6.43 plain login sequence.
        """
        sentence = ["/login", f"=name={self.username}", f"=password={self.password}"]
        res = self._talk(sentence)
        if res and res[0].get("reply") == "!done":
            return True
        logger.warning("MikroTik login authentication failed.")
        return False

    def get_interface_stats(self) -> List[Dict[str, Any]]:
        """
        Queries RouterOS for interface traffic counters via /interface/print.
        Returns list of dicts with interface status and byte counters.
        """
        if not self.sock:
            if not self.connect():
                return []

        sentence = [
            "/interface/print",
            "=.proplist=name,rx-byte,tx-byte,running,disabled"
        ]

        raw_reply = self._talk(sentence)
        results: List[Dict[str, Any]] = []

        for item in raw_reply:
            if item.get("reply") == "!re":
                name = item.get("name")
                if not name:
                    continue
                rx_bytes = int(item.get("rx-byte", 0))
                tx_bytes = int(item.get("tx-byte", 0))
                running = item.get("running") == "true"
                disabled = item.get("disabled") == "true"
                
                status = "running" if (running and not disabled) else "down"

                results.append({
                    "name": name,
                    "rx_bytes": rx_bytes,
                    "tx_bytes": tx_bytes,
                    "status": status
                })

        return results

    def get_active_pppoe_sessions(self) -> List[Dict[str, str]]:
        """
        Queries RouterOS for active PPPoE sessions via /ppp/active/print.
        Returns list of dicts with session info: name, address, caller-id, uptime.
        """
        if not self.sock:
            if not self.connect():
                raise MikrotikAPIError(f"Failed to connect to MikroTik host {self.host}:{self.port}")

        sentence = [
            "/ppp/active/print",
            "=.proplist=name,service,caller-id,address,uptime"
        ]

        try:
            raw_reply = self._talk(sentence)
        except Exception as e:
            logger.warning(f"Error querying /ppp/active/print, attempting reconnect: {e}")
            self.close()
            if not self.connect():
                raise MikrotikAPIError(f"Failed to reconnect to MikroTik host {self.host}:{self.port}")
            raw_reply = self._talk(sentence)

        sessions: List[Dict[str, str]] = []
        for item in raw_reply:
            if item.get("reply") == "!re":
                name = item.get("name")
                if name:
                    sessions.append({
                        "name": name.strip(),
                        "address": item.get("address", "").strip(),
                        "caller_id": item.get("caller-id", "").strip(),
                        "uptime": item.get("uptime", "").strip(),
                        "service": item.get("service", "").strip()
                    })

        return sessions

    def get_active_pppoe(self) -> List[str]:
        """
        Queries RouterOS for active PPPoE sessions via /ppp/active/print (tambah_fitur.md Section 8 & 29).
        Returns list of active PPPoE usernames.
        """
        sessions = self.get_active_pppoe_sessions()
        return [s["name"] for s in sessions if s.get("name")]


    def _talk(self, sentence: List[str]) -> List[Dict[str, str]]:
        """
        Sends a sentence and reads the response array from RouterOS API.
        """
        if not self.sock:
            raise MikrotikAPIError("Socket connection is closed.")

        self._write_sentence(sentence)
        return self._read_response()

    def _write_sentence(self, sentence: List[str]) -> None:
        for word in sentence:
            self._write_word(word)
        self._write_word("") # Empty word marks end of sentence

    def _write_word(self, word: str) -> None:
        b_word = word.encode("utf-8")
        b_len = self._encode_length(len(b_word))
        self.sock.sendall(b_len + b_word)

    def _read_response(self) -> List[Dict[str, str]]:
        response: List[Dict[str, str]] = []
        current_dict: Dict[str, str] = {}

        while True:
            sentence = self._read_sentence()
            if not sentence:
                break
            reply_type = sentence[0]
            if reply_type == "!trap":
                # API error response
                break
            if reply_type == "!re":
                item_dict = {"reply": "!re"}
                for word in sentence[1:]:
                    if word.startswith("="):
                        parts = word[1:].split("=", 1)
                        key = parts[0]
                        val = parts[1] if len(parts) > 1 else ""
                        item_dict[key] = val
                response.append(item_dict)
            elif reply_type == "!done":
                item_dict = {"reply": "!done"}
                for word in sentence[1:]:
                    if word.startswith("="):
                        parts = word[1:].split("=", 1)
                        key = parts[0]
                        val = parts[1] if len(parts) > 1 else ""
                        item_dict[key] = val
                response.append(item_dict)
                break
        return response

    def _read_sentence(self) -> List[str]:
        sentence: List[str] = []
        while True:
            word = self._read_word()
            if word == "":
                break
            sentence.append(word)
        return sentence

    def _read_word(self) -> str:
        length = self._read_length()
        if length == 0:
            return ""
        buf = bytearray()
        while len(buf) < length:
            chunk = self.sock.recv(length - len(buf))
            if not chunk:
                raise MikrotikAPIError("Connection lost while reading word.")
            buf.extend(chunk)
        return buf.decode("utf-8", errors="ignore")

    def _encode_length(self, length: int) -> bytes:
        if length < 0x80:
            return bytes([length])
        elif length < 0x4000:
            length |= 0x8000
            return struct.pack(">H", length)
        elif length < 0x200000:
            length |= 0xC00000
            return struct.pack(">I", length)[1:]
        elif length < 0x10000000:
            length |= 0xE0000000
            return struct.pack(">I", length)
        else:
            return bytes([0xF0]) + struct.pack(">I", length)

    def _read_length(self) -> int:
        b1 = self.sock.recv(1)
        if not b1:
            return 0
        l1 = b1[0]
        if (l1 & 0x80) == 0:
            return l1
        elif (l1 & 0xC0) == 0x80:
            l2 = self.sock.recv(1)[0]
            return ((l1 & 0x3F) << 8) | l2
        elif (l1 & 0xE0) == 0xC0:
            b_rest = self.sock.recv(2)
            return ((l1 & 0x1F) << 16) | (b_rest[0] << 8) | b_rest[1]
        elif (l1 & 0xF0) == 0xE0:
            b_rest = self.sock.recv(3)
            return ((l1 & 0x0F) << 24) | (b_rest[0] << 16) | (b_rest[1] << 8) | b_rest[2]
        elif l1 == 0xF0:
            b_rest = self.sock.recv(4)
            return struct.unpack(">I", b_rest)[0]
        return 0
