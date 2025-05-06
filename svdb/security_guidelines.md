# SVDB Security Guidelines

## Private Key Management

SVDB interacts with the blockchain for transaction signing. Proper management of private keys is critical for system security. This document outlines the security measures and best practices for private key management.

### Current Implementation

SVDB uses a secure approach for handling private keys:

1. **Hardware Security Module (HSM) Integration**:
   - Private keys are stored in secure HSMs, never in application code
   - Multiple HSM providers supported (AWS KMS, Azure Key Vault, GCP KMS)
   - Secure transaction signing occurs inside the HSM
   - Implementation instructions:
     ```
     # In .env file
     USE_HSM=true
     HSM_PROVIDER=aws  # or azure, gcp
     HSM_CONFIG_PATH=/path/to/hsm_config.json
     ```

2. **Environment-Based Key Configuration**:
   - HSM configuration parameters stored in environment variables via `.env` file
   - The `.env` file is excluded from version control via `.gitignore`
   - No sensitive credentials in code or version control

3. **Separation of Duties**:
   - API service has no direct access to keys
   - Only the blockchain bridge module interacts with the HSM
   - Signing operations are isolated and logged

4. **Key Rotation**:
   - System supports key rotation without service disruption
   - Rotation API endpoint for administrative use
   - Automatic alerting on key rotation events

### Security Best Practices

The following security practices are implemented for production deployment:

1. **HSM Provider Configuration**:
   - AWS KMS:
     ```
     # Required environment variables
     AWS_REGION=us-east-1
     AWS_KMS_KEY_ID=mrk-5ebc733b55af4ef2889de2aa8bfa5949
     ```
   
   - Azure Key Vault:
     ```
     # Required environment variables
     AZURE_VAULT_URL=https://your-vault.vault.azure.net/
     AZURE_KEY_NAME=transaction-signing-key
     ```
   
   - Google Cloud KMS:
     ```
     # Required environment variables
     GCP_PROJECT_ID=your-project-id
     GCP_KEY_RING=blockchain-keys
     GCP_KEY_NAME=transaction-signing-key
     ```

2. **Key Encryption at Rest**:
   - All keys are encrypted at rest inside the HSM
   - No unencrypted private keys are ever stored or transmitted

3. **Access Controls**:
   - Role-based access control for HSM operations
   - Multi-factor authentication for administrative HSM access
   - Principle of least privilege for application service accounts

### Blockchain Transaction Signing Process

The secure transaction signing workflow:

1. Transaction is prepared with relevant data (file hash, metadata)
2. Transaction data is serialized to JSON format
3. Request for signing is sent to the HSM
4. HSM performs the signing operation and returns the signature
5. Signed transaction is submitted to the blockchain
6. Private key never leaves the secure HSM environment

### Monitoring and Alerting

The system includes comprehensive monitoring for key security:

1. **Real-time Alerting**:
   - Email alerts for signing failures
   - Notification on key rotation events
   - Critical alerts for unauthorized access attempts

2. **Audit Logging**:
   - All HSM operations are logged with timestamps
   - Key usage is tracked for compliance and security
   - Log shipping to secure storage for compliance needs

### Emergency Procedures

In case of key compromise:

1. **Immediate Actions**:
   - Revoke the compromised key using admin tools
   - Rotate to backup key using the rotation API
   - Notify appropriate stakeholders
   - Begin incident response procedure

2. **Recovery**:
   - Generate new secure keys in HSM
   - Re-verify recent transactions for integrity
   - Document the incident and remediation steps

## Implementation Status

All required security measures have been implemented:

- [x] HSM integration with multiple provider support
- [x] Key rotation mechanism
- [x] Alert system for key-related issues
- [x] Audit logging of key operations
- [x] Secure transaction signing process
- [x] Error handling for HSM failures
- [x] Access controls and principle of least privilege

## Conclusion

By implementing these security measures, SVDB maintains a high level of security for private key management. This approach aligns with industry best practices and ensures the integrity of blockchain transactions while protecting sensitive cryptographic material.

**Note**: This document should be reviewed and updated quarterly to reflect the latest security practices and technologies. 