from argon2 import PasswordHasher, exceptions
import secrets, random, string

# So we have an object to work with
class Password(object):
    def __init__(self, plaintext, salt = None, hash: str = None) -> None:
        self.plaintext = plaintext
        self.salt = str(secrets.token_bytes(16)) if not salt else salt

        self.hash = hash

    def _hash(self, hasher):
        self.hash = hasher.hash(f"{self.salt}|{self.plaintext}")

    def verify_hash(self, hasher, hash_to_check): 
        compiled = f"{self.salt}|{self.plaintext}"
        return hasher.verify(hash_to_check, compiled)


class Hasher:
    def __init__(self):
        self.password_hasher = PasswordHasher() 

    def hash_password(self, password_plaintext):
        password = Password(plaintext=password_plaintext)
        password._hash(self.password_hasher)
        return password

    def verify_password_hash(self, password_plaintext, password_hash, password_salt):
        try:
            return self.password_hasher.verify(password_hash, f"{password_salt}|{password_plaintext}")
        except exceptions.VerifyMismatchError:
            return False
        
