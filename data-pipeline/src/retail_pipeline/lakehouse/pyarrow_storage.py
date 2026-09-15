"""ObjectStorage on pyarrow filesystems: S3-compatible services or local directories."""

import shutil
from pathlib import Path
from typing import Self

import pyarrow as pa
from pyarrow import fs as pa_fs

_COPY_BUFFER_BYTES = 8 * 1024 * 1024


class PyArrowObjectStorage:
    """Treats the first path segment of a pyarrow filesystem as the bucket."""

    def __init__(self, filesystem: pa_fs.FileSystem, *, creates_parent_directories: bool) -> None:
        self._filesystem = filesystem
        self._creates_parent_directories = creates_parent_directories

    @classmethod
    def for_s3(cls, endpoint: str, region: str, access_key_id: str, secret_access_key: str) -> Self:
        scheme, separator, authority = endpoint.partition("://")
        if not separator:
            scheme, authority = "https", endpoint
        filesystem = pa_fs.S3FileSystem(
            access_key=access_key_id,
            secret_key=secret_access_key,
            region=region,
            scheme=scheme,
            endpoint_override=authority,
            allow_bucket_creation=True,
        )
        # S3 has no directories; creating them would only add empty marker objects.
        return cls(filesystem, creates_parent_directories=False)

    @classmethod
    def for_local_directory(cls, root: Path) -> Self:
        root.mkdir(parents=True, exist_ok=True)
        filesystem = pa_fs.SubTreeFileSystem(str(root), pa_fs.LocalFileSystem())
        return cls(filesystem, creates_parent_directories=True)

    def ensure_bucket(self, bucket: str) -> bool:
        if self._filesystem.get_file_info(bucket).type != pa_fs.FileType.NotFound:
            return False
        self._filesystem.create_dir(bucket)
        return True

    def upload_file(self, bucket: str, key: str, path: Path) -> None:
        with path.open("rb") as source, self._open_output_stream(bucket, key) as target:
            shutil.copyfileobj(source, target, _COPY_BUFFER_BYTES)

    def write_text(self, bucket: str, key: str, text: str) -> None:
        with self._open_output_stream(bucket, key) as target:
            target.write(text.encode("utf-8"))

    def read_text(self, bucket: str, key: str) -> str:
        with self._filesystem.open_input_stream(_object_path(bucket, key)) as source:
            return source.read().decode("utf-8")

    def exists(self, bucket: str, key: str) -> bool:
        file_info = self._filesystem.get_file_info(_object_path(bucket, key))
        return file_info.type == pa_fs.FileType.File

    def open_input_stream(self, bucket: str, key: str) -> pa.NativeFile:
        return self._filesystem.open_input_stream(_object_path(bucket, key))

    def _open_output_stream(self, bucket: str, key: str) -> pa.NativeFile:
        path = _object_path(bucket, key)
        if self._creates_parent_directories:
            self._filesystem.create_dir(path.rsplit("/", 1)[0], recursive=True)
        return self._filesystem.open_output_stream(path)


def _object_path(bucket: str, key: str) -> str:
    return f"{bucket}/{key.lstrip('/')}"
