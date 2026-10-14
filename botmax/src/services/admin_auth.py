"""Authentication and brute-force protection service for BotMAX Admin Panel with multi-tenant support"""

import hashlib
import hmac
import logging
import secrets
import time
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger("botmax.auth")


class AdminAuthService:
    """Manages admin credentials, secure session tokens, and brute-force protection for SuperAdmin and Admins"""

    def __init__(self, admin_password: str, secret_key: str, db: Optional[Any] = None):
        self.admin_password = admin_password
        self.secret_key = secret_key
        self.db = db
        # Active sessions: token -> {"expires_at": float, "admin": Dict[str, Any]}
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        # Rate limiting: ip -> [attempts, lock_until_timestamp]
        self._login_attempts: Dict[str, Dict[str, float]] = {}

    def _cleanup_expired(self) -> None:
        """Remove expired session tokens and old rate limit records"""
        now = time.time()
        # Clean sessions
        self._active_sessions = {
            t: s for t, s in self._active_sessions.items() if s.get("expires_at", 0) > now
        }
        # Clean attempts older than 10 minutes
        self._login_attempts = {
            ip: data for ip, data in self._login_attempts.items()
            if data.get("lock_until", 0) > now or (now - data.get("last_attempt", 0) < 600)
        }

    def _check_brute_force(self, client_ip: str, now: float) -> Optional[Tuple[bool, str, Optional[str]]]:
        """Check if IP is currently locked due to too many failed attempts"""
        attempt_info = self._login_attempts.get(client_ip, {"count": 0, "lock_until": 0})
        if attempt_info.get("lock_until", 0) > now:
            remaining = int(attempt_info["lock_until"] - now)
            logger.warning(f"Login blocked for IP {client_ip}. Remaining lock: {remaining}s")
            return (
                False,
                f"Слишком много неверных попыток. Доступ заблокирован на {remaining} сек.",
                None,
            )
        return None

    def _record_failed_attempt(self, client_ip: str, now: float) -> Tuple[bool, str, Optional[str]]:
        """Register a failed login attempt and apply lock if threshold exceeded"""
        attempt_info = self._login_attempts.get(client_ip, {"count": 0, "lock_until": 0})
        attempt_info["count"] = attempt_info.get("count", 0) + 1
        attempt_info["last_attempt"] = now
        if attempt_info["count"] >= 5:
            attempt_info["lock_until"] = now + 60
            self._login_attempts[client_ip] = attempt_info
            logger.warning(f"IP {client_ip} exceeded 5 failed login attempts. Locked for 60s.")
            return (
                False,
                "Превышено количество попыток. Доступ временно заблокирован на 60 секунд.",
                None,
            )

        self._login_attempts[client_ip] = attempt_info
        attempts_left = 5 - attempt_info["count"]
        return False, f"Неверный пароль или логин администратора. Осталось попыток: {attempts_left}", None

    def _generate_token(self, admin_dict: Dict[str, Any], now: float, client_ip: str) -> str:
        """Issue cryptographically signed session token for admin"""
        if client_ip in self._login_attempts:
            del self._login_attempts[client_ip]

        random_entropy = secrets.token_hex(24)
        timestamp = str(int(now))
        payload = f"admin:{admin_dict.get('id', 'admin')}:{timestamp}:{random_entropy}".encode("utf-8")
        signature = hmac.new(self.secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        token = f"bmx_{signature[:32]}_{random_entropy[:16]}"

        expires_at = now + 604800  # 7 days
        self._active_sessions[token] = {
            "expires_at": expires_at,
            "admin": admin_dict,
        }
        logger.info(f"Admin session established for {admin_dict.get('username')} ({admin_dict.get('role')}) from IP {client_ip}")
        return token

    async def authenticate(
        self,
        username: Optional[str],
        password: str,
        client_ip: str = "unknown",
    ) -> Tuple[bool, str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Authenticate admin against database or fallback credentials.
        Returns: (success, message, token_or_none, admin_info_or_none)
        """
        self._cleanup_expired()
        now = time.time()

        locked = self._check_brute_force(client_ip, now)
        if locked:
            return locked[0], locked[1], locked[2], None

        target_username = (username or "superadmin").strip().lower()
        admin_record = None

        if self.db:
            try:
                admin_record = await self.db.get_admin_by_username(target_username)
            except Exception as e:
                logger.error(f"Error querying admin from DB: {e}")

        # Check DB admin record
        if admin_record:
            from ..database.db import Database
            is_valid = Database.verify_password(
                password=password,
                salt=admin_record["password_salt"],
                expected_hash=admin_record["password_hash"],
            )
            if is_valid and admin_record.get("is_active", 1):
                admin_info = {
                    "id": admin_record["id"],
                    "username": admin_record["username"],
                    "display_name": admin_record["display_name"],
                    "role": admin_record["role"],
                    "sbp_phone": admin_record["sbp_phone"],
                    "sbp_bank": admin_record["sbp_bank"],
                }
                token = self._generate_token(admin_info, now, client_ip)
                return True, "Авторизация успешна", token, admin_info

        # Fallback superadmin password verification
        if target_username in ("superadmin", "", "admin"):
            is_super = secrets.compare_digest(
                password.strip().encode("utf-8"),
                self.admin_password.strip().encode("utf-8"),
            )
            if is_super:
                super_info = {
                    "id": "admin_super",
                    "username": "superadmin",
                    "display_name": "Главный Администратор",
                    "role": "superadmin",
                    "sbp_phone": "+7 (999) 000-00-00",
                    "sbp_bank": "СБП / Т-Банк",
                }
                token = self._generate_token(super_info, now, client_ip)
                return True, "Авторизация успешна", token, super_info

        fail_ok, fail_msg, _ = self._record_failed_attempt(client_ip, now)
        return fail_ok, fail_msg, None, None

    def login(
        self,
        password: str,
        client_ip: str = "unknown",
        username: Optional[str] = "superadmin",
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Synchronous authentication for fallback and backward compatibility with unit tests.
        Returns: (success, message, token_or_none)
        """
        self._cleanup_expired()
        now = time.time()

        locked = self._check_brute_force(client_ip, now)
        if locked:
            return locked

        is_correct = secrets.compare_digest(
            password.strip().encode("utf-8"),
            self.admin_password.strip().encode("utf-8"),
        )
        if not is_correct:
            return self._record_failed_attempt(client_ip, now)

        admin_info = {
            "id": "admin_super",
            "username": (username or "superadmin").strip().lower(),
            "display_name": "Главный Администратор",
            "role": "superadmin",
            "sbp_phone": "+7 (999) 000-00-00",
            "sbp_bank": "СБП / Т-Банк",
        }
        token = self._generate_token(admin_info, now, client_ip)
        return True, "Авторизация успешна", token

    def verify_token(self, token: Optional[str]) -> bool:
        """Verify if a session token is active and not expired"""
        return self.get_session_admin(token) is not None

    def get_session_admin(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Retrieve authenticated admin details from active token"""
        if not token:
            return None

        self._cleanup_expired()
        session = self._active_sessions.get(token)
        if not session:
            return None

        if session.get("expires_at", 0) < time.time():
            del self._active_sessions[token]
            return None

        return session.get("admin")

    def logout(self, token: Optional[str]) -> None:
        """Revoke a session token"""
        if token and token in self._active_sessions:
            del self._active_sessions[token]
            logger.info("Admin session revoked on logout.")

