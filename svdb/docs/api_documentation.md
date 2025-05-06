# SVDB API Documentation

## Overview

SVDB provides a secure, decentralized storage solution with blockchain verification. This documentation covers the REST API endpoints available for Web2 integrations.

## Authentication

All API requests require authentication using an API key.

```
Header: X-API-Key: your_api_key_here
```

API keys can be configured in the `.env` file of your SVDB deployment.

## Endpoints

### Health Check

```
GET /health
```

Returns the current status of the API.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2023-05-06T20:14:13.296Z",
  "version": "1.0.0"
}
```

### Store File

```
POST /store
```

Upload a file to SVDB. The file will be hashed, stored, and the hash will be submitted to the blockchain.

**Request:**
- Content-Type: multipart/form-data
- Body: 
  - file: The file to store

**Response:**
```json
{
  "hash": "c97195f3fca2764f95fcdadaf129c6bd0d3612d41cd464eb82d6293b4d3d910933604c9752717f6ec40970418d3c224432abc45a2d2151dcaaa53981a5d8f056",
  "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "status": "pending"
}
```

- `hash`: The unique hash identifier of the stored file
- `tx_hash`: The blockchain transaction hash (if available)
- `status`: Status of the transaction ("pending", "submitted", "error")

### Retrieve File

```
GET /retrieve/{file_hash}
```

Download a file by its hash.

**Parameters:**
- `file_hash`: The hash of the file to retrieve

**Response:**
- The file content
- Appropriate Content-Type header based on the file type

### Verify File

```
GET /verify/{file_hash}
```

Verify the blockchain status of a file.

**Parameters:**
- `file_hash`: The hash of the file to verify

**Response:**
```json
{
  "hash": "c97195f3fca2764f95fcdadaf129c6bd0d3612d41cd464eb82d6293b4d3d910933604c9752717f6ec40970418d3c224432abc45a2d2151dcaaa53981a5d8f056",
  "verified": true,
  "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "block_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
  "timestamp": 1683403453,
  "metadata": {
    "filename": "example.pdf",
    "content_type": "application/pdf",
    "size": 1024,
    "timestamp": 1683403400
  }
}
```

- `verified`: Whether the file is verified on the blockchain
- `tx_hash`: The blockchain transaction hash
- `block_hash`: The blockchain block hash (if confirmed)
- `timestamp`: Timestamp of blockchain confirmation
- `metadata`: Additional file metadata

## Integration Examples

### Python Example

```python
import requests

API_URL = "https://your-svdb-instance.com"
API_KEY = "your_api_key_here"

# Upload a file
def upload_file(file_path):
    with open(file_path, 'rb') as f:
        response = requests.post(
            f"{API_URL}/store",
            files={"file": f},
            headers={"X-API-Key": API_KEY}
        )
    return response.json()

# Retrieve a file
def retrieve_file(file_hash, save_path):
    response = requests.get(
        f"{API_URL}/retrieve/{file_hash}",
        headers={"X-API-Key": API_KEY}
    )
    
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    return False

# Verify a file
def verify_file(file_hash):
    response = requests.get(
        f"{API_URL}/verify/{file_hash}",
        headers={"X-API-Key": API_KEY}
    )
    return response.json()
```

### Node.js Example

```javascript
const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');

const API_URL = "https://your-svdb-instance.com";
const API_KEY = "your_api_key_here";

// Upload a file
async function uploadFile(filePath) {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  
  const response = await axios.post(`${API_URL}/store`, form, {
    headers: {
      ...form.getHeaders(),
      'X-API-Key': API_KEY
    }
  });
  
  return response.data;
}

// Retrieve a file
async function retrieveFile(fileHash, savePath) {
  const response = await axios.get(`${API_URL}/retrieve/${fileHash}`, {
    headers: { 'X-API-Key': API_KEY },
    responseType: 'stream'
  });
  
  const writer = fs.createWriteStream(savePath);
  response.data.pipe(writer);
  
  return new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
}

// Verify a file
async function verifyFile(fileHash) {
  const response = await axios.get(`${API_URL}/verify/${fileHash}`, {
    headers: { 'X-API-Key': API_KEY }
  });
  
  return response.data;
}
```

## Web2 Integration Guide

### Getting Started

1. **Obtain API Credentials**
   - Contact your SVDB administrator to get an API key
   - Configure your environment with the API key

2. **Choose Integration Method**
   - Direct API calls (examples above)
   - Use one of the cloud adapters (S3, Azure, GCP, DigitalOcean)

3. **Test Your Integration**
   - Use the `/health` endpoint to verify connectivity
   - Upload a test file and verify it can be retrieved

### Using Cloud Adapters

SVDB provides adapters for common cloud storage providers that handle the communication with the SVDB API:

```python
# AWS S3 Example
from svdb.integrations.cloud_adapters import S3Adapter

adapter = S3Adapter(
    svdb_api_url="https://your-svdb-instance.com",
    svdb_api_key="your_api_key_here",
    aws_access_key="your_aws_access_key",
    aws_secret_key="your_aws_secret_key",
    bucket_name="your-bucket"
)

# Import objects from S3 to SVDB
adapter.import_objects(prefix="documents/")

# Verify objects in SVDB
verification_results = adapter.verify_objects(prefix="documents/")
```

Similar adapters are available for Azure Blob Storage, Google Cloud Storage, and DigitalOcean Spaces.

### Best Practices

1. **Error Handling**
   - Implement proper error handling for API responses
   - Set up retry logic for temporary failures
   - Monitor blockchain verification status

2. **Performance Optimization**
   - For large files, consider chunking uploads
   - Implement parallel uploads for multiple files
   - Use batch operations when available

3. **Security**
   - Store API keys securely
   - Use HTTPS for all API calls
   - Implement rate limiting to prevent abuse

4. **Monitoring**
   - Log API responses for troubleshooting
   - Set up alerts for failed uploads or verifications
   - Monitor transaction status for important files

## Support

For integration support, contact support@svdb.example.com or refer to the main documentation at our [GitHub repository](https://github.com/yourusername/svdb). 