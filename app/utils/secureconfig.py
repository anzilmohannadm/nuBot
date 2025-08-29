import os
import base64
import configparser
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class ConfigParserCrypt(configparser.ConfigParser):
    '''A ConfigParser subclass with AES-GCM encryption for secure config storage.'''

    def __init__(self, *args, encryption_key=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Load encryption key from environment variable or generate a new one
        self.encryption_key =  encryption_key or self._load_or_generate_key()

        # encryption prefix "ENC::"
        self.sigil = "ENC::"

    def _load_or_generate_key(self):
        '''Load encryption key from an environment variable or generate a new one.'''
        key_env_var = "CONFIG_ENCRYPTION_KEY"

        if key_env_var in os.environ:
            return base64.urlsafe_b64decode(os.environ[key_env_var])

        # Generate a new AES-256 key if not found
        new_key = AESGCM.generate_key(bit_length=256)
        print(f"Generated new encryption key (Base64): {base64.urlsafe_b64encode(new_key).decode()}")
        return new_key

    def _encrypt(self, plaintext):
        '''Encrypt a value using AES-GCM.'''
        aesgcm = AESGCM(self.encryption_key)
        nonce = os.urandom(12)  # 96-bit nonce
        
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        return self.sigil + base64.urlsafe_b64encode(nonce + ciphertext).decode()

    def _decrypt(self, encrypted_value):
        '''Decrypt a value using AES-GCM.'''
        if not encrypted_value or not encrypted_value.startswith(self.sigil):
            return encrypted_value
        
        encrypted_value = encrypted_value[len(self.sigil):]  # Remove prefix
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_value)

        nonce, ciphertext = encrypted_bytes[:12], encrypted_bytes[12:]  # Split nonce and ciphertext

        aesgcm = AESGCM(self.encryption_key)
        return aesgcm.decrypt(nonce, ciphertext, None).decode()

    def get(self, section, option, raw=False, fallback=None):
        '''Get a value, decrypting if necessary.'''
        raw_value = super().get(section, option, raw=raw, fallback=fallback)
        return self._decrypt(raw_value)

    def set(self, section, option, value, encrypt=False):
        '''Set a value, encrypting if needed.'''
        if encrypt:
            value = self._encrypt(value)
        super().set(section, option, value)

    def print_decrypted(self):
        '''Print all decrypted config values.'''
        print("\n Decrypted ini file")
        for section in self.sections():
            print(f"[{section}]")
            for key in self.options(section):
                print(f"{key} = {self.get(section, key)} \n")
            print()

    def print_encrypted(self):
        """Print all encrypted values in the configuration."""
        print("\n Encrypted ini file")
        for section in self.sections():
            print(f"[{section}]")
            for key, value in self.items(section):
                print(f"{key}= {value}")  # Print stored (encrypted) values
            


# === Example Usage ===
if __name__ == "__main__":
    config = ConfigParserCrypt()

    # Add a section and store encrypted and plaintext values
    config.add_section("test_section")
    config.set("test_section", "option", "40000", encrypt=True) # encrypt True if it sensitive info like passwords,keys

    #  Print encrypted config to store
    config.print_encrypted()
    
    # Print decrypted config for debugging
    config.print_decrypted()
    

