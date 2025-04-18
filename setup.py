from setuptools import setup, find_packages

setup(
    name="vault",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "bitwarden-sdk",
        "keyring>=23.0.0",
        "cryptography>=36.0.0",
    ],
    description="A simple Python package for managing Bitwarden secrets",
    author="Toru AI",
    author_email="info@toruai.com",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
