"""
MySQL 8.0+ 데이터베이스 설정.

환경 변수로 모든 설정을 오버라이드할 수 있다.
"""
from __future__ import annotations

import os
from typing import Any, Dict


class DatabaseConfig:
    """MySQL 연결 설정."""

    def __init__(self) -> None:
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", 3306))
        self.database = os.getenv("DB_NAME", "bankruptcy_auction")
        self.user = os.getenv("DB_USER", "root")
        self.password = os.getenv("DB_PASSWORD", "")
        self.charset = os.getenv("DB_CHARSET", "utf8mb4")
        self.connection_timeout = int(os.getenv("DB_CONNECTION_TIMEOUT", 30))

    def get_connection_params(self) -> Dict[str, Any]:
        """PyMySQL 연결 파라미터."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "charset": self.charset,
            "connect_timeout": self.connection_timeout,
            "autocommit": False,
        }

    def __repr__(self) -> str:
        return f"DatabaseConfig(host={self.host}, port={self.port}, database={self.database})"


db_config = DatabaseConfig()

DATABASE_CONFIG = db_config.get_connection_params()
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")
