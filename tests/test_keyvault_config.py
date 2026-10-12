"""
Unit tests for Azure Key Vault secret resolution and tenant environment structural key parity.
"""

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import Settings


def test_tenant_env_structural_key_parity():
    """Verify 100% structural key parity across all tenant .env files in tenants/."""
    all_keys = set()
    file_keys = {}
    
    for root, dirs, files in os.walk("tenants"):
        for file in files:
            if ".env" in file:
                path = os.path.join(root, file)
                keys = []
                with open(path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k = line.split("=", 1)[0].strip()
                            keys.append(k)
                            all_keys.add(k)
                file_keys[path] = set(keys)
                
    assert len(file_keys) == 10, f"Expected 10 tenant .env files, found {len(file_keys)}"
    
    for path, keys in file_keys.items():
        missing = all_keys - keys
        assert not missing, f"File {path} is missing keys: {missing}"
        assert len(keys) == len(all_keys), f"Key count mismatch in {path}: {len(keys)} vs {len(all_keys)}"


def test_keyvault_dynamic_secret_fetching():
    """Test dynamic fetching of secrets from Azure Key Vault when env vars are missing."""
    mock_secret = MagicMock()
    mock_secret.value = "secret-from-keyvault-123"
    
    mock_client = MagicMock()
    mock_client.get_secret.return_value = mock_secret
    
    mock_kv_mod = MagicMock()
    mock_kv_mod.SecretClient.return_value = mock_client
    
    mock_id_mod = MagicMock()
    
    with sys.modules.setdefault("azure.identity", mock_id_mod), \
         sys.modules.setdefault("azure.keyvault.secrets", mock_kv_mod):
        
        # Override mock module attributes in case azure package was partially loaded
        import types
        azure_mod = sys.modules.get("azure", types.ModuleType("azure"))
        azure_kv = types.ModuleType("keyvault")
        azure_kv_secrets = types.ModuleType("secrets")
        azure_kv_secrets.SecretClient = MagicMock(return_value=mock_client)
        
        azure_identity = types.ModuleType("identity")
        azure_identity.DefaultAzureCredential = MagicMock()
        
        sys.modules["azure"] = azure_mod
        sys.modules["azure.identity"] = azure_identity
        sys.modules["azure.keyvault"] = azure_kv
        sys.modules["azure.keyvault.secrets"] = azure_kv_secrets
        
        test_settings = Settings(
            AZURE_KEY_VAULT_NAME="test-kv-name",
            AZURE_KEY_VAULT_SECRET_SQL_PASSWORD="test-sql-secret",
            AZURE_KEY_VAULT_SECRET_OPENAI_KEY="test-openai-secret",
            AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR="test-storage-secret",
            AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD="test-pg-secret",
            AZURE_SQL_PASSWORD=None,
            AZURE_OPENAI_API_KEY=None,
            AZURE_STORAGE_CONNECTION_STRING=None,
            POSTGRES_PASSWORD=None,
        )
        
        assert test_settings.AZURE_SQL_PASSWORD == "secret-from-keyvault-123"
        assert test_settings.AZURE_OPENAI_API_KEY == "secret-from-keyvault-123"
        assert test_settings.AZURE_STORAGE_CONNECTION_STRING == "secret-from-keyvault-123"
        assert test_settings.POSTGRES_PASSWORD == "secret-from-keyvault-123"


if __name__ == "__main__":
    test_tenant_env_structural_key_parity()
    test_keyvault_dynamic_secret_fetching()
    print("ALL KEYVAULT CONFIG TESTS PASSED SUCCESSFULLY!")
