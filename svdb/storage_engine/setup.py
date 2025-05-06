from setuptools import setup, find_packages

setup(
    name="svdb_core",
    version="0.1.0",
    description="SVDB Storage Engine",
    author="SVDB Team",
    packages=find_packages(),
    package_dir={"": "python"},
    python_requires=">=3.8",
    install_requires=[
        "cryptography>=37.0.0",  # For fallback hashing 
    ],
    entry_points={
        'console_scripts': [
            'svdb-core=svdb_core.__main__:main',
        ],
    },
) 