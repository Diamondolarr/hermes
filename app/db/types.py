from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


class EmbeddingType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, dimension: int):
        super().__init__()
        self.dimension = dimension

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import VECTOR

            return dialect.type_descriptor(VECTOR(self.dimension))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        if hasattr(value, "tolist"):
            value = value.tolist()

        return [float(item) for item in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        if hasattr(value, "tolist"):
            value = value.tolist()

        return [float(item) for item in value]
