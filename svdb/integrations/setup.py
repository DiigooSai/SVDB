#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="svdb-integrations",
    version="0.1.0",
    description="Web2 integration tools for SVDB",
    author="SVDB Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "boto3>=1.24.0",
        "httpx>=0.24.0",
        "click>=8.1.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "all": [
            "azure-storage-blob>=12.14.0",
            "google-cloud-storage>=2.7.0",
            "tqdm>=4.64.0",
        ],
        "aws": [],  # boto3 is in the base requirements
        "azure": ["azure-storage-blob>=12.14.0"],
        "gcp": ["google-cloud-storage>=2.7.0"],
        "do": [],  # Uses boto3 which is in the base requirements
    },
    entry_points={
        "console_scripts": [
            "svdb-import=svdb.integrations.import_tool:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 