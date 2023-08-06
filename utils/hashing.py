from __future__ import annotations

import secrets

from argon2 import PasswordHasher, exceptions


class Password(object):
    """A class for interacting with passwords.

    Args:
        plaintext (str): The plaintext password.
        salt (str, optional): The salt to use for the password. Defaults to None.
        hash (str, optional): The hash to use for the password. Defaults to None.
    """

    def __init__(self, plaintext, salt=None, hash: str = None) -> None:
        self.plaintext = plaintext
        self.salt = str(secrets.token_bytes(16)) if not salt else salt

        self.hash = hash

    def _hash(self, hasher):
        """Hashes the password.

        Args:
            hasher (PasswordHasher): The hasher to use."""
        self.hash = hasher.hash(f"{self.salt}|{self.plaintext}")

    def verify_hash(self, hasher, hash_to_check):
        """Verifies a hash.

        Args:
            hasher (PasswordHasher): The hasher to use.
            hash_to_check (str): The hash to check.
        """
        compiled = f"{self.salt}|{self.plaintext}"
        return hasher.verify(hash_to_check, compiled)


class Hasher:
    """A class for interacting with passwords.

    Args:
        plaintext (str): The plaintext password.
    """

    def __init__(self):
        self.password_hasher = PasswordHasher()

    def hash_password(self, password_plaintext: str) -> Password:
        """Hashes a password.

        Args:
            password_plaintext (str): The plaintext password.

        Returns:
            Password: The hashed password.
        """
        password = Password(plaintext=password_plaintext)
        password._hash(self.password_hasher)
        return password

    def verify_password_hash(self, password_plaintext: str, password_hash: str, password_salt: str) -> bool:
        """Verifies a password hash.

        Args:
            password_plaintext (str): The plaintext password.
            password_hash (str): The hash to check.
            password_salt (str): The salt to use.
        """
        try:
            return self.password_hasher.verify(password_hash, f"{password_salt}|{password_plaintext}")
        except exceptions.VerifyMismatchError:
            return False
