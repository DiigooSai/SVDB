"""
Utility functions for the storage engine core.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

def ensure_directory(path: str) -> None:
    """
    Ensure a directory exists.
    
    Args:
        path: Directory path to create
    """
    os.makedirs(path, exist_ok=True)
    
def read_json_file(path: str) -> Dict[str, Any]:
    """
    Read a JSON file.
    
    Args:
        path: Path to the JSON file
        
    Returns:
        The parsed JSON data
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
def write_json_file(path: str, data: Dict[str, Any]) -> None:
    """
    Write a dictionary to a JSON file.
    
    Args:
        path: Path to the JSON file
        data: Data to write
    """
    with open(path, 'w') as f:
        json.dump(data, f)
        
def list_files(directory: str, pattern: Optional[str] = None) -> List[Path]:
    """
    List files in a directory with an optional pattern.
    
    Args:
        directory: Directory to list files from
        pattern: Optional glob pattern
        
    Returns:
        List of Path objects
    """
    path = Path(directory)
    if not path.exists():
        return []
    
    if pattern:
        return list(path.glob(pattern))
    else:
        return [p for p in path.iterdir() if p.is_file()]
        
def format_size(size_bytes: int) -> str:
    """
    Format a size in bytes to a human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable size string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB" 