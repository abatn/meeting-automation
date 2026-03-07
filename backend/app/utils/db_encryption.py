from sqlalchemy.types import TypeDecorator, String, Text
from app.utils.encryption import encrypt_data, decrypt_data


class EncryptedString(TypeDecorator):
    """
    A SQLAlchemy TypeDecorator that encrypts data on the way into the DB
    and decrypts it on the way out.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_data(str(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return decrypt_data(value)
            except Exception:
                # Fallback for unencrypted legacy data during migration
                return value
        return value


class EncryptedText(TypeDecorator):
    """
    Same as EncryptedString, but backed by Text for longer content.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_data(str(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return decrypt_data(value)
            except Exception:
                return value
        return value
