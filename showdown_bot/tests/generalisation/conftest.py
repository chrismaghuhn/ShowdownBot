import pytest

from .real_fixture import run_real_fixture


@pytest.fixture(scope="session")
def generated_report_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("generalisation") / "report"
    run_real_fixture(out)
    return out
