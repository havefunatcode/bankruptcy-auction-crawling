"""
Database configuration for PostgreSQL connection
"""
import os
from typing import Dict, Any


class DatabaseConfig:
    """PostgreSQL database configuration"""
    
    def __init__(self):
        # Docker PostgreSQL default settings
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = int(os.getenv('DB_PORT', 5432))
        self.database = os.getenv('DB_NAME', 'bankruptcy_auction')
        self.user = os.getenv('DB_USER', 'postgres')
        self.password = os.getenv('DB_PASSWORD', 'postgres')
        
        # Connection pool settings
        self.min_connections = int(os.getenv('DB_MIN_CONNECTIONS', 1))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', 10))
        
        # Connection timeout settings
        self.connection_timeout = int(os.getenv('DB_CONNECTION_TIMEOUT', 30))
        self.command_timeout = int(os.getenv('DB_COMMAND_TIMEOUT', 60))
        
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters as dict"""
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password,
            'connect_timeout': self.connection_timeout,
        }
    
    def get_async_connection_string(self) -> str:
        """Get PostgreSQL async connection string"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def __repr__(self) -> str:
        return f"DatabaseConfig(host={self.host}, port={self.port}, database={self.database})"


# Global database configuration instance
db_config = DatabaseConfig()

# Database configuration constants
DATABASE_CONFIG = {
    'host': db_config.host,
    'port': db_config.port,
    'database': db_config.database,
    'user': db_config.user,
    'password': db_config.password,
    'connect_timeout': db_config.connection_timeout,
}

# Schema file path
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), 'schema.sql')