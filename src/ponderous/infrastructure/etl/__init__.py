"""ETL (Extract, Transform, Load) pipelines for external data sources."""

from .collection_transformer import normalize_collection_data

# Removed moxfield_source import - API functionality deleted

__all__: list[str] = [
    "normalize_collection_data",
]
