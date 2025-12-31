import os
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import logging

logger = logging.getLogger(__name__)

class AzureStorageHelper:
    def __init__(self, connection_string=None, account_url=None):
        try:
            if connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            elif account_url:
                self.blob_service_client = BlobServiceClient(account_url, credential=DefaultAzureCredential())
            else:
                # Fallback to env var
                conn_str = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
                if conn_str:
                    self.blob_service_client = BlobServiceClient.from_connection_string(conn_str)
                else:
                    logger.warning("Azure Storage credentials not provided. Local storage will be used as fallback.")
                    self.blob_service_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob Service Client: {e}")
            self.blob_service_client = None

    def upload_blob(self, container_name, blob_name, data):
        if not self.blob_service_client:
            return False
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            if not container_client.exists():
                container_client.create_container()
            
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(data, overwrite=True)
            return True
        except Exception as e:
            logger.error(f"Error uploading blob {blob_name} to container {container_name}: {e}")
            return False

    def download_blob(self, container_name, blob_name):
        if not self.blob_service_client:
            return None
        try:
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            return blob_client.download_blob().readall()
        except Exception as e:
            logger.error(f"Error downloading blob {blob_name} from container {container_name}: {e}")
            return None

    def list_blobs(self, container_name):
        if not self.blob_service_client:
            return []
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            return [blob.name for blob in container_client.list_blobs()]
        except Exception as e:
            logger.error(f"Error listing blobs in container {container_name}: {e}")
            return []

class AzureKeyVaultHelper:
    def __init__(self, vault_url=None):
        if not vault_url:
            vault_url = os.environ.get('AZURE_KEYVAULT_URL')
        
        if vault_url:
            try:
                self.client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
            except Exception as e:
                logger.error(f"Failed to initialize Key Vault Client: {e}")
                self.client = None
        else:
            self.client = None

    def get_secret(self, secret_name):
        if not self.client:
            return os.environ.get(secret_name)
        try:
            return self.client.get_secret(secret_name).value
        except Exception as e:
            logger.error(f"Error retrieving secret {secret_name}: {e}")
            return os.environ.get(secret_name)
