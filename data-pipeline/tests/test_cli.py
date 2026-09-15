from pathlib import Path

from retail_pipeline.cli import main


def test_main_with_sample_command_writes_files_and_exits_zero(tmp_path: Path) -> None:
    exit_code = main(["sample", "dunnhumby", "--output-dir", str(tmp_path), "--seed", "3"])

    assert exit_code == 0
    assert (tmp_path / "transaction_data.csv").is_file()


def test_main_with_missing_input_dir_exits_with_error(tmp_path: Path) -> None:
    exit_code = main(["ingest", "dunnhumby", "--input-dir", str(tmp_path / "missing")])

    assert exit_code == 1
