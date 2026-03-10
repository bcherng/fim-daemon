#!/usr/bin/env python3
"""
Cryptographic functions for FIM Device Signing
"""
import os
import json
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

class DeviceSigner:
    """Manages device keys and signatures"""
    
    def __init__(self, key_dir):
        self.key_dir = key_dir
        self.private_key_path = os.path.join(key_dir, 'device_private.pem')
        self.public_key_path = os.path.join(key_dir, 'device_public.pem')
        self.private_key = None
        self.public_key = None
        
        self.load_or_generate_keys()
        
    def load_or_generate_keys(self):
        """Load existing keys or generate new ones"""
        if os.path.exists(self.private_key_path) and os.path.exists(self.public_key_path):
            with open(self.private_key_path, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )
            with open(self.public_key_path, 'rb') as f:
                self.public_key = serialization.load_pem_public_key(
                    f.read()
                )
        else:
            self.generate_keys()
            
    def generate_keys(self):
        """Generate a new RSA key pair"""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.public_key = self.private_key.public_key()
        
        # Save keys
        os.makedirs(self.key_dir, exist_ok=True)
        
        # Write private key with restricted permissions
        private_pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Try to restrict file permissions
        fd = os.open(self.private_key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.write(fd, private_pem)
        os.close(fd)
        
        public_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(self.public_key_path, 'wb') as f:
            f.write(public_pem)
            
    def get_public_key_pem(self):
        """Return the public key as a PEM string"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
    def sign_payload(self, payload_string):
        """Sign a payload string and return hex signature"""
        if not self.private_key:
            return None
            
        signature = self.private_key.sign(
            payload_string.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return signature.hex()
