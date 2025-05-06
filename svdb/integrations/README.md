# SVDB Web2 Integrations

This package provides tools for integrating SVDB with various Web2 storage services.

## Features

- Cloud storage adapters for:
  - Amazon S3
  - Azure Blob Storage
  - Google Cloud Storage
  - DigitalOcean Spaces
- Import tools for migrating data from cloud storage to SVDB
- Consistent API across different storage providers

## Installation

```bash
# Install basic package
pip install -e .

# Install with all cloud provider dependencies
pip install -e ".[all]"

# Or install with specific cloud provider dependencies
pip install -e ".[aws]"  # For AWS S3
pip install -e ".[azure]"  # For Azure Blob Storage
pip install -e ".[gcp]"  # For Google Cloud Storage
pip install -e ".[do]"  # For DigitalOcean Spaces
```

## Usage

### Importing from AWS S3

```python
from svdb.integrations.cloud_adapters import S3Adapter

# Initialize adapter
adapter = S3Adapter(
    bucket_name="my-bucket",
    aws_access_key_id="YOUR_ACCESS_KEY",  # Optional
    aws_secret_access_key="YOUR_SECRET_KEY",  # Optional
    region_name="us-east-1"  # Optional
)

# Connect to S3
if adapter.connect():
    # List files
    files = adapter.list_files(prefix="data/")
    print(f"Found {len(files)} files")
    
    # Import a file to SVDB
    file_hash, tx_hash = adapter.import_file("data/myfile.txt", "./svdb_data")
    print(f"Imported file: {file_hash} (tx: {tx_hash})")
    
    # Import multiple files
    results = adapter.import_files(["data/file1.txt", "data/file2.txt"], "./svdb_data")
    for file_key, (file_hash, tx_hash) in results.items():
        print(f"{file_key} -> {file_hash} (tx: {tx_hash})")
```

### Using the Command-Line Tool

```bash
# Import a specific file from S3
svdb-import s3 --file my-bucket/path/to/file.txt --db-path ./svdb_data

# Import all files with a prefix
svdb-import s3 --prefix data/ --db-path ./svdb_data

# Import files listed in a file
svdb-import s3 --file-list files.txt --db-path ./svdb_data

# Use a config file
svdb-import s3 --config s3_config.json --db-path ./svdb_data

# Import from Azure Blob Storage
svdb-import azure --prefix images/ --db-path ./svdb_data
```

## Configuration

### Environment Variables

AWS S3:
- `AWS_S3_BUCKET`: S3 bucket name
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_REGION`: AWS region name

Azure Blob Storage:
- `AZURE_STORAGE_ACCOUNT`: Storage account name
- `AZURE_STORAGE_CONTAINER`: Container name
- `AZURE_STORAGE_KEY`: Account key
- `AZURE_STORAGE_CONNECTION_STRING`: Connection string

Google Cloud Storage:
- `GCP_STORAGE_BUCKET`: GCS bucket name
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to credentials file
- `GCP_PROJECT_ID`: GCP project ID

DigitalOcean Spaces:
- `DO_SPACES_NAME`: Space name
- `DO_SPACES_REGION`: Region (e.g., nyc3)
- `DO_SPACES_KEY`: Spaces key
- `DO_SPACES_SECRET`: Spaces secret

### Configuration File

Example `config.json`:

```json
{
  "bucket": "my-bucket",
  "access_key_id": "YOUR_ACCESS_KEY",
  "secret_access_key": "YOUR_SECRET_KEY",
  "region": "us-east-1"
}
```

## Extending

To add support for a new storage provider:

1. Create a new adapter class that inherits from `CloudStorageAdapter`
2. Implement all required methods
3. Add your adapter to the imports in `cloud_adapters/__init__.py` 