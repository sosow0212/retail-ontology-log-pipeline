from retail_pipeline.lakehouse.pyarrow_storage import PyArrowObjectStorage


def test_ensure_bucket_run_twice_reports_creation_once(storage: PyArrowObjectStorage) -> None:
    assert storage.ensure_bucket("raw") is True
    assert storage.ensure_bucket("raw") is False


def test_write_text_with_nested_key_can_be_read_back(storage: PyArrowObjectStorage) -> None:
    storage.ensure_bucket("raw")

    storage.write_text("raw", "nested/key/file.json", '{"ok": true}')

    assert storage.read_text("raw", "nested/key/file.json") == '{"ok": true}'
    assert storage.exists("raw", "nested/key/file.json")
    assert not storage.exists("raw", "nested/key/missing.json")
