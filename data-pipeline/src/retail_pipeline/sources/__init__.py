"""Source table specifications, keyed by source name."""

from retail_pipeline.sources.dunnhumby import DUNNHUMBY_SOURCE, DUNNHUMBY_TABLES
from retail_pipeline.sources.table_spec import SourceTable

SOURCE_TABLES: dict[str, tuple[SourceTable, ...]] = {DUNNHUMBY_SOURCE: DUNNHUMBY_TABLES}
