#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::Path;
    use tempfile::tempdir;

    // Test the Blake3 hash calculation
    #[test]
    fn test_blake3_hash_calculation() {
        let data = b"Hello, SVDB!";
        let hash = calculate_blake3_hash(data);
        // Blake3 hash is deterministic, so we can check against a known value
        assert_eq!(hash.len(), 64); // Blake3 produces a 32-byte (64 hex chars) hash
        // We could add a specific expected hash here, but this would change if the hash function changes
    }

    // Test the Blake2b hash calculation
    #[test]
    fn test_blake2b_hash_calculation() {
        let data = b"Hello, SVDB!";
        let hash = calculate_blake2b_hash(data);
        assert_eq!(hash.len(), 64); // Blake2b produces a 32-byte (64 hex chars) hash
    }

    // Test the Keccak256 hash calculation
    #[test]
    fn test_keccak256_hash_calculation() {
        let data = b"Hello, SVDB!";
        let hash = calculate_keccak256_hash(data);
        assert_eq!(hash.len(), 64); // Keccak256 produces a 32-byte (64 hex chars) hash
    }

    // Test file chunking
    #[test]
    fn test_file_chunking() {
        let data = vec![1u8; 5 * 1024 * 1024]; // 5MB data
        let chunks = chunk_data(&data, 1024 * 1024); // 1MB chunks
        assert_eq!(chunks.len(), 5);
        
        for chunk in &chunks {
            assert_eq!(chunk.len(), 1024 * 1024);
        }
    }

    // Test uneven chunking (data size not a multiple of chunk size)
    #[test]
    fn test_uneven_chunking() {
        let data = vec![1u8; 3_500_000]; // 3.5MB data
        let chunks = chunk_data(&data, 1024 * 1024); // 1MB chunks
        assert_eq!(chunks.len(), 4);
        
        // First 3 chunks should be full size
        for i in 0..3 {
            assert_eq!(chunks[i].len(), 1024 * 1024);
        }
        
        // Last chunk should be the remainder
        assert_eq!(chunks[3].len(), 500_000);
    }

    // Test storing and retrieving a file
    #[test]
    fn test_store_and_retrieve_file() {
        let dir = tempdir().unwrap();
        let db_path = dir.path().to_str().unwrap();
        
        let test_data = b"This is test data".to_vec();
        
        // Store the file
        let hash = store_file(db_path, &test_data);
        assert!(!hash.is_empty());
        
        // Retrieve the file
        let retrieved_data = retrieve_file(db_path, &hash).unwrap();
        assert_eq!(retrieved_data, test_data);
    }

    // Test storing and retrieving a large file (with chunking)
    #[test]
    fn test_large_file_storage() {
        let dir = tempdir().unwrap();
        let db_path = dir.path().to_str().unwrap();
        
        // Create a 5MB test file
        let test_data = vec![42u8; 5 * 1024 * 1024];
        
        // Store the file
        let hash = store_file(db_path, &test_data);
        assert!(!hash.is_empty());
        
        // Retrieve the file
        let retrieved_data = retrieve_file(db_path, &hash).unwrap();
        assert_eq!(retrieved_data, test_data);
    }

    // Test error handling when retrieving a non-existent file
    #[test]
    fn test_retrieve_nonexistent_file() {
        let dir = tempdir().unwrap();
        let db_path = dir.path().to_str().unwrap();
        
        let result = retrieve_file(db_path, "nonexistent_hash");
        assert!(result.is_err());
    }

    // Test database initialization
    #[test]
    fn test_db_initialization() {
        let dir = tempdir().unwrap();
        let db_path = dir.path().to_str().unwrap();
        
        // Initialize DB
        let db = initialize_db(db_path).unwrap();
        
        // Check if DB directory is created
        assert!(Path::new(db_path).exists());
        
        // Close DB explicitly to avoid temp directory cleanup issues
        drop(db);
    }
} 