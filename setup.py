from setuptools import setup, find_packages

setup(
    name="toru-vault",
    version="0.1.4",
    packages=["toru_vault"],
    install_requires=[
        "bitwarden-sdk",
        "cryptography>=36.0.0",
    ],
    extras_require={
        "keyring": ["keyring>=23.0.0"],
    },
    description="ToruVault: A simple Python package for managing Bitwarden secrets",
    author="Toru AI",
    author_email="dev@toruai.com",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
