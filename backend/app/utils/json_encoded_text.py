import json
from sqlalchemy.types import TypeDecorator, Text
from sqlalchemy.ext.mutable import MutableList

class JSONEncodedText(TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value

MutableList.associate_with(JSONEncodedText)