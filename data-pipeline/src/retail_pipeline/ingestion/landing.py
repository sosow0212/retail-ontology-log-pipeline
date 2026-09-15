"""Raw landing zone: copy source files to object storage with a manifest describing the batch."""

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from retail_pipeline.errors import ManifestError, MissingSourceFileError
from retail_pipeline.lakehouse.object_storage import ObjectStorage
from retail_pipeline.sources.table_spec import SourceTable

logger = logging.getLogger(__name__)

MANIFEST_FILE_NAME = "_manifest.json"
_READ_CHUNK_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class FileStats:
    size_bytes: int
    sha256: str
    row_count: int


@dataclass(frozen=True, slots=True)
class LandedFile:
    table: str
    object_key: str
    size_bytes: int
    sha256: str
    row_count: int


@dataclass(frozen=True, slots=True)
class LandingManifest:
    source: str
    batch_id: str
    landed_at: str
    files: tuple[LandedFile, ...]

    def file_for(self, table: SourceTable) -> LandedFile:
        """Return the landed file of a table or raise ManifestError when it is absent."""
        for landed_file in self.files:
            if landed_file.table == table.name:
                return landed_file
        raise ManifestError(f"batch {self.batch_id} has no landed file for table {table.name}")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> Self:
        try:
            payload = json.loads(text)
            return cls(
                source=payload["source"],
                batch_id=payload["batch_id"],
                landed_at=payload["landed_at"],
                files=tuple(LandedFile(**item) for item in payload["files"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ManifestError(f"invalid landing manifest: {error}") from error


def new_batch_id(now: datetime) -> str:
    """Return a sortable UTC batch identifier such as 20260915T103000Z."""
    return now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def batch_prefix(source: str, batch_id: str) -> str:
    return f"{source}/batch_id={batch_id}"


def describe_csv_file(path: Path) -> FileStats:
    """Return the size, SHA-256 digest, and data row count of a CSV file.

    Rows are counted as lines minus the header, which assumes no quoted field contains a
    line break. The dunnhumby files satisfy this, and bronze verification catches violations.
    """
    digest = hashlib.sha256()
    size_bytes = 0
    newline_count = 0
    last_byte = b""
    with path.open("rb") as file:
        while chunk := file.read(_READ_CHUNK_BYTES):
            digest.update(chunk)
            size_bytes += len(chunk)
            newline_count += chunk.count(b"\n")
            last_byte = chunk[-1:]
    has_unterminated_last_line = size_bytes > 0 and last_byte != b"\n"
    line_count = newline_count + int(has_unterminated_last_line)
    return FileStats(
        size_bytes=size_bytes, sha256=digest.hexdigest(), row_count=max(line_count - 1, 0)
    )


def land_source_files(
    storage: ObjectStorage,
    bucket: str,
    source: str,
    tables: Sequence[SourceTable],
    input_dir: Path,
    batch_id: str,
    landed_at: datetime,
) -> LandingManifest:
    """Upload every declared source file and write the manifest last.

    A batch without a manifest is incomplete, so readers only trust batches that have one.

    Raises:
        MissingSourceFileError: A declared file is absent; nothing is uploaded in that case.
    """
    paths = {table.name: input_dir / table.file_name for table in tables}
    missing_paths = sorted(str(path) for path in paths.values() if not path.is_file())
    if missing_paths:
        raise MissingSourceFileError(f"missing source files: {', '.join(missing_paths)}")

    storage.ensure_bucket(bucket)
    prefix = batch_prefix(source, batch_id)
    landed_files: list[LandedFile] = []
    for table in tables:
        stats = describe_csv_file(paths[table.name])
        object_key = f"{prefix}/{table.file_name}"
        storage.upload_file(bucket, object_key, paths[table.name])
        landed_files.append(
            LandedFile(
                table=table.name,
                object_key=object_key,
                size_bytes=stats.size_bytes,
                sha256=stats.sha256,
                row_count=stats.row_count,
            )
        )
        logger.info("landed s3://%s/%s (%d rows)", bucket, object_key, stats.row_count)

    manifest = LandingManifest(
        source=source,
        batch_id=batch_id,
        landed_at=landed_at.astimezone(UTC).isoformat(),
        files=tuple(landed_files),
    )
    storage.write_text(bucket, f"{prefix}/{MANIFEST_FILE_NAME}", manifest.to_json())
    return manifest
