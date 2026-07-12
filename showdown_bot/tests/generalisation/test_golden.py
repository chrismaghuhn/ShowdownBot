from pathlib import Path


def test_report_matches_golden(generated_report_dir):
    golden = Path(__file__).with_name("golden")
    assert (generated_report_dir / "report.json").read_bytes() == (golden / "report.json").read_bytes()
    assert (generated_report_dir / "report.md").read_bytes() == (golden / "report.md").read_bytes()
