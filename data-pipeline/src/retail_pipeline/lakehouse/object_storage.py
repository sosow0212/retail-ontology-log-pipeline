"""Port for bucket/key object access used by landing and bronze loading."""

from pathlib import Path
from typing import Protocol

import pyarrow as pa


class ObjectStorage(Protocol):
    def ensure_bucket(self, bucket: str) -> bool:
        """Create the bucket when it is missing and return True if it was created."""
        ...

    def upload_file(self, bucket: str, key: str, path: Path) -> None:
        """Copy a local file to bucket/key."""
        ...

    def write_text(self, bucket: str, key: str, text: str) -> None:
        """Write UTF-8 text to bucket/key."""
        ...

    def read_text(self, bucket: str, key: str) -> str:
        """Read UTF-8 text from bucket/key."""
        ...

    def exists(self, bucket: str, key: str) -> bool:
        """Return True when bucket/key is an existing object."""
        ...

    def open_input_stream(self, bucket: str, key: str) -> pa.NativeFile:
        """Open bucket/key for sequential reading."""
        ...
