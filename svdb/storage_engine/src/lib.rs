use pyo3::prelude::*;
use pyo3::types::PyBytes;
use thiserror::Error;
use std::path::Path;
use std::sync::Arc;
use std::collections::HashMap;
use std::sync::Mutex;
use rocksdb::{DB, Options};
use blake2::{Blake2b512, Digest as Blake2Digest};
use sha3::Keccak256;
use digest::Digest;

// Constants
const DEFAULT_CHUNK_SIZE: usize = 1024 * 1024; // 1MB chunks
const HASH_ALGORITHM_BLAKE3: &str = "blake3";
const HASH_ALGORITHM_BLAKE2B: &str = "blake2b";
const HASH_ALGORITHM_KECCAK: &str = "keccak256";

#[derive(Error, Debug)]
pub enum StorageError {
    #[error("IO error: {0}")]
    IOError(#[from] std::io::Error),
    
    #[error("Database error: {0}")]
    DBError(#[from] rocksdb::Error),
    
    #[error("Hash not found: {0}")]
    HashNotFound(String),
    
    #[error("Serialization error: {0}")]
    SerializationError(String),
    
    #[error("Invalid algorithm: {0}")]
    InvalidAlgorithm(String),
    
    #[error("Chunking error: {0}")]
    ChunkingError(String),
}

pub type Result<T> = std::result::Result<T, StorageError>;

/// Represents the hash algorithm to use
#[derive(Clone, Copy, Debug)]
pub enum HashAlgorithm {
    Blake3,
    Blake2b,
    Keccak256,
}

impl HashAlgorithm {
    pub fn from_str(s: &str) -> Result<Self> {
        match s.to_lowercase().as_str() {
            HASH_ALGORITHM_BLAKE3 => Ok(HashAlgorithm::Blake3),
            HASH_ALGORITHM_BLAKE2B => Ok(HashAlgorithm::Blake2b),
            HASH_ALGORITHM_KECCAK => Ok(HashAlgorithm::Keccak256),
            _ => Err(StorageError::InvalidAlgorithm(s.to_string())),
        }
    }
    
    pub fn as_str(&self) -> &'static str {
        match self {
            HashAlgorithm::Blake3 => HASH_ALGORITHM_BLAKE3,
            HashAlgorithm::Blake2b => HASH_ALGORITHM_BLAKE2B,
            HashAlgorithm::Keccak256 => HASH_ALGORITHM_KECCAK,
        }
    }
}

impl Default for HashAlgorithm {
    fn default() -> Self {
        HashAlgorithm::Blake3
    }
}

/// Metadata for a stored file
#[derive(serde::Serialize, serde::Deserialize, Debug, Clone)]
pub struct FileMetadata {
    pub hash: String,
    pub algorithm: String,
    pub size: usize,
    pub chunk_size: usize,
    pub chunks: Vec<String>,
    pub timestamp: u64,
}

/// Represents a chunked file
pub struct ChunkedFile {
    pub metadata: FileMetadata,
    pub chunks: Vec<Vec<u8>>,
}

/// Storage Engine handles storing and retrieving files
pub struct StorageEngine {
    db: Arc<DB>,
    cache: Arc<Mutex<HashMap<String, Vec<u8>>>>,
}

impl StorageEngine {
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self> {
        let mut opts = Options::default();
        opts.create_if_missing(true);
        let db = DB::open(&opts, path)?;
        
        Ok(StorageEngine {
            db: Arc::new(db),
            cache: Arc::new(Mutex::new(HashMap::new())),
        })
    }
    
    /// Store a file with default settings (blake3, no chunking)
    pub fn store(&self, data: &[u8]) -> Result<String> {
        self.store_with_options(data, HashAlgorithm::Blake3, 0)
    }
    
    /// Store a file with specified options
    pub fn store_with_options(&self, data: &[u8], algorithm: HashAlgorithm, chunk_size: usize) -> Result<String> {
        if chunk_size > 0 && data.len() > chunk_size {
            // Chunked storage
            let chunked_file = chunk_data(data, chunk_size, algorithm)?;
            
            // Store metadata
            let metadata_key = format!("meta:{}", chunked_file.metadata.hash);
            let metadata_bytes = serde_json::to_vec(&chunked_file.metadata)
                .map_err(|e| StorageError::SerializationError(e.to_string()))?;
            
            self.db.put(metadata_key.as_bytes(), &metadata_bytes)?;
            
            // Store each chunk
            for (i, chunk) in chunked_file.chunks.iter().enumerate() {
                let chunk_key = format!("chunk:{}:{}", chunked_file.metadata.hash, i);
                self.db.put(chunk_key.as_bytes(), chunk)?;
            }
            
            Ok(chunked_file.metadata.hash)
        } else {
            // Simple storage
            let hash = calculate_hash_with_algorithm(data, algorithm);
            self.db.put(hash.as_bytes(), data)?;
            
            // Update cache
            let mut cache = self.cache.lock().unwrap();
            cache.insert(hash.clone(), data.to_vec());
            
            Ok(hash)
        }
    }
    
    /// Retrieve a file by its hash
    pub fn retrieve(&self, hash: &str) -> Result<Vec<u8>> {
        // Try cache first
        let cache = self.cache.lock().unwrap();
        if let Some(data) = cache.get(hash) {
            return Ok(data.clone());
        }
        drop(cache);
        
        // Check if this is a chunked file
        let metadata_key = format!("meta:{}", hash);
        if let Some(metadata_bytes) = self.db.get(metadata_key.as_bytes())? {
            // Chunked file - reassemble
            let metadata: FileMetadata = serde_json::from_slice(&metadata_bytes)
                .map_err(|e| StorageError::SerializationError(e.to_string()))?;
            
            let mut data = Vec::with_capacity(metadata.size);
            
            for i in 0..metadata.chunks.len() {
                let chunk_key = format!("chunk:{}:{}", hash, i);
                if let Some(chunk) = self.db.get(chunk_key.as_bytes())? {
                    data.extend_from_slice(&chunk);
                } else {
                    return Err(StorageError::ChunkingError(format!("Chunk {} not found", i)));
                }
            }
            
            // Update cache
            let mut cache = self.cache.lock().unwrap();
            cache.insert(hash.to_string(), data.clone());
            
            Ok(data)
        } else {
            // Simple file
            match self.db.get(hash.as_bytes())? {
                Some(data) => {
                    // Update cache
                    let mut cache = self.cache.lock().unwrap();
                    cache.insert(hash.to_string(), data.clone());
                    Ok(data)
                },
                None => Err(StorageError::HashNotFound(hash.to_string())),
            }
        }
    }
}

/// Chunk data into smaller pieces and hash them
fn chunk_data(data: &[u8], chunk_size: usize, algorithm: HashAlgorithm) -> Result<ChunkedFile> {
    // Use default chunk size if specified size is too small
    let chunk_size = if chunk_size < 1024 { DEFAULT_CHUNK_SIZE } else { chunk_size };
    
    let mut chunks = Vec::new();
    let mut chunk_hashes = Vec::new();
    
    // Split the data into chunks
    for chunk in data.chunks(chunk_size) {
        let chunk_hash = calculate_hash_with_algorithm(chunk, algorithm);
        chunk_hashes.push(chunk_hash);
        chunks.push(chunk.to_vec());
    }
    
    // Create a combined hash of all chunks
    let combined_data = chunk_hashes.join("|").into_bytes();
    let file_hash = calculate_hash_with_algorithm(&combined_data, algorithm);
    
    let metadata = FileMetadata {
        hash: file_hash.clone(),
        algorithm: algorithm.as_str().to_string(),
        size: data.len(),
        chunk_size,
        chunks: chunk_hashes,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs(),
    };
    
    Ok(ChunkedFile { metadata, chunks })
}

/// Calculate hash using the default algorithm (blake3)
pub fn calculate_hash(data: &[u8]) -> String {
    calculate_hash_with_algorithm(data, HashAlgorithm::Blake3)
}

/// Calculate hash using the specified algorithm
pub fn calculate_hash_with_algorithm(data: &[u8], algorithm: HashAlgorithm) -> String {
    match algorithm {
        HashAlgorithm::Blake3 => {
            let hash = blake3::hash(data);
            hash.to_hex().to_string()
        },
        HashAlgorithm::Blake2b => {
            let mut hasher = Blake2b512::new();
            hasher.update(data);
            let result = hasher.finalize();
            hex::encode(result)
        },
        HashAlgorithm::Keccak256 => {
            let mut hasher = Keccak256::new();
            hasher.update(data);
            let result = hasher.finalize();
            hex::encode(result)
        },
    }
}

// Python module
#[pymodule]
fn svdb_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_store_file, m)?)?;
    m.add_function(wrap_pyfunction!(py_retrieve_file, m)?)?;
    m.add_function(wrap_pyfunction!(py_calculate_hash, m)?)?;
    m.add_function(wrap_pyfunction!(py_store_file_with_options, m)?)?;
    m.add_function(wrap_pyfunction!(py_calculate_hash_with_algorithm, m)?)?;
    Ok(())
}

// Python bindings
#[pyfunction]
fn py_store_file(_py: Python, db_path: &str, py_data: &PyBytes) -> PyResult<String> {
    let data = py_data.as_bytes();
    
    let engine = StorageEngine::new(db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    
    engine.store(data)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
}

#[pyfunction]
fn py_store_file_with_options(
    _py: Python, 
    db_path: &str, 
    py_data: &PyBytes,
    algorithm: &str,
    chunk_size: usize
) -> PyResult<String> {
    let data = py_data.as_bytes();
    
    let algorithm = HashAlgorithm::from_str(algorithm)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
    
    let engine = StorageEngine::new(db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    
    engine.store_with_options(data, algorithm, chunk_size)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
}

#[pyfunction]
fn py_retrieve_file(py: Python, db_path: &str, hash: &str) -> PyResult<Py<PyBytes>> {
    let engine = StorageEngine::new(db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    
    engine.retrieve(hash)
        .map(|data| PyBytes::new(py, &data).into())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
}

#[pyfunction]
fn py_calculate_hash(_py: Python, py_data: &PyBytes) -> String {
    let data = py_data.as_bytes();
    calculate_hash(data)
}

#[pyfunction]
fn py_calculate_hash_with_algorithm(_py: Python, py_data: &PyBytes, algorithm: &str) -> PyResult<String> {
    let data = py_data.as_bytes();
    let algo = HashAlgorithm::from_str(algorithm)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
    
    Ok(calculate_hash_with_algorithm(data, algo))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;
    
    #[test]
    fn test_storage_engine() -> Result<()> {
        let temp_dir = tempdir()?;
        let engine = StorageEngine::new(temp_dir.path())?;
        
        let test_data = b"Hello, SVDB!";
        let hash = engine.store(test_data)?;
        
        let retrieved = engine.retrieve(&hash)?;
        assert_eq!(retrieved, test_data);
        
        Ok(())
    }
    
    #[test]
    fn test_calculate_hash() {
        let data = b"Hello, SVDB!";
        let hash = calculate_hash(data);
        assert!(!hash.is_empty());
        
        // Hash should be deterministic
        let hash2 = calculate_hash(data);
        assert_eq!(hash, hash2);
    }
    
    #[test]
    fn test_calculate_hash_with_algorithm() {
        let data = b"Hello, SVDB!";
        
        // Test all algorithms
        let hash_blake3 = calculate_hash_with_algorithm(data, HashAlgorithm::Blake3);
        let hash_blake2b = calculate_hash_with_algorithm(data, HashAlgorithm::Blake2b);
        let hash_keccak = calculate_hash_with_algorithm(data, HashAlgorithm::Keccak256);
        
        // All should produce non-empty results
        assert!(!hash_blake3.is_empty());
        assert!(!hash_blake2b.is_empty());
        assert!(!hash_keccak.is_empty());
        
        // Different algorithms should produce different hashes
        assert_ne!(hash_blake3, hash_blake2b);
        assert_ne!(hash_blake3, hash_keccak);
        assert_ne!(hash_blake2b, hash_keccak);
    }
    
    #[test]
    fn test_chunking() -> Result<()> {
        // Generate a larger test file
        let large_data = vec![0u8; 5 * 1024 * 1024]; // 5MB
        let chunk_size = 1024 * 1024; // 1MB
        
        // Chunk the data
        let chunked = chunk_data(&large_data, chunk_size, HashAlgorithm::Blake3)?;
        
        // Should have 5 chunks
        assert_eq!(chunked.chunks.len(), 5);
        assert_eq!(chunked.metadata.chunks.len(), 5);
        
        Ok(())
    }
    
    #[test]
    fn test_store_retrieve_chunked() -> Result<()> {
        let temp_dir = tempdir()?;
        let engine = StorageEngine::new(temp_dir.path())?;
        
        // Generate test data larger than chunk size
        let large_data = vec![1u8; 3 * 1024 * 1024]; // 3MB
        let chunk_size = 1024 * 1024; // 1MB chunks
        
        // Store with chunking
        let hash = engine.store_with_options(&large_data, HashAlgorithm::Blake3, chunk_size)?;
        
        // Retrieve
        let retrieved = engine.retrieve(&hash)?;
        
        // Verify
        assert_eq!(retrieved, large_data);
        
        Ok(())
    }
}
