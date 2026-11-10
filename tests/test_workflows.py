import glob
import yaml


def test_all_workflows_parse_and_have_jobs():
    files = glob.glob(".github/workflows/*.yml")
    assert files
    for f in files:
        doc = yaml.safe_load(open(f, encoding="utf-8"))
        assert doc.get("jobs"), f
