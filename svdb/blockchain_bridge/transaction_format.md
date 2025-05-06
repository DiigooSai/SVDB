# SVDB Blockchain Transaction Format

## Overview
This document outlines the transaction format used by SVDB for blockchain integration. The blockchain team has reviewed and confirmed these formats for compatibility with ArthaChain.

## Transaction Payload Format

Confirmed transaction payload format for ArthaChain:

```json
{
  "file_hash": "hash_string_here",
  "uploader": "user_id_or_unknown",
  "timestamp": 1683403453,
  "metadata": {
    "filename": "example.pdf",
    "content_type": "application/pdf",
    "size": 1024,
    "custom_field": "custom_value"
  }
}
```

### Field Descriptions

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| file_hash | string | The Blake3 hash of the file | Yes |
| uploader | string | User ID or "unknown" | Yes |
| timestamp | integer | Unix timestamp of upload time | Yes |
| metadata | object | Additional file metadata | Yes |

### Metadata Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| filename | string | Original filename | No |
| content_type | string | MIME type of the file | No |
| size | integer | File size in bytes | No |
| custom_field | string | Any custom metadata | No |

## Transaction Response Format

Confirmed response format from ArthaChain:

```json
{
  "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "status": "pending"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| tx_hash | string | The blockchain transaction hash |
| status | string | Initial status ("pending", "submitted", "error") |

## Verification Request Format

Format for transaction status verification:

```
GET /api/transactions/{tx_hash}
```

Expected response:

```json
{
  "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
  "file_hash": "hash_string_here",
  "status": "confirmed",
  "block_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
  "block_number": 12345678,
  "timestamp": 1683403453
}
```

## Blockchain Team Confirmation

The blockchain team has reviewed and confirmed the following details:

1. ✅ Transaction payload format is accepted without modifications
2. ✅ No additional fields are required in the payload
3. ✅ Response format matches the blockchain API expectations
4. ✅ Transaction rate limit: 100 transactions per minute
5. ✅ Expected confirmation times: 30-60 seconds under normal network conditions
6. ✅ Error codes to handle:
   - 1001: Insufficient funds
   - 1002: Gas price too low
   - 1003: Nonce mismatch
   - 1004: Transaction rejected
   - 2001: Network error

## Contact

For questions or clarifications, please contact the SVDB development team at dev@svdb.example.com. 