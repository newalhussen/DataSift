import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import config, store
from app.analysis import analyze, infer_column, missing_mask
from app.cleaning import CleaningError, CleanOptions, clean, neutralize_formulas
from app.main import app, parse_csv

CSV = (
    "id,name,age,joined,score\n"
    "1,Ann,34,2024-01-05,88.5\n"
    "2,Bob,,2024-02-10,92\n"
    "3,Cy,abc,2024-03-15,75\n"
    "3,Cy,abc,2024-03-15,75\n"
    "4, Dee ,41,2024-04-20,N/A\n"
    "5,Eve,29,2024-05-25,60\n"
)


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "ds")
    monkeypatch.setattr(store.config, "UPLOAD_DIR", tmp_path / "ds")
    yield


@pytest.fixture
def df():
    return parse_csv(CSV.encode())[0]


class TestAnalysis:
    def test_overview(self, df):
        a = analyze(df)
        assert (a["rows"], a["columns"]) == (6, 5)
        assert a["duplicateRows"] == 1
        assert a["missingCells"] == 2  # blank age, "N/A" score
        assert 0 < a["score"] < 100

    def test_column_types(self, df):
        cols = {c["name"]: c for c in analyze(df)["columnReports"]}
        assert cols["id"]["type"] == "integer"
        assert cols["joined"]["type"] == "datetime"
        assert cols["score"]["type"] == "float"
        assert cols["name"]["type"] == "text"

    def test_inconsistent_values_are_reported(self):
        lines = ["id,age"] + [f"{i},{20 + i}" for i in range(9)] + ["9,abc"]
        d = parse_csv(chr(10).join(lines).encode())[0]
        a = analyze(d)
        age = {c["name"]: c for c in a["columnReports"]}["age"]
        assert age["type"] == "integer" and age["inconsistent"] == 1 and age["inconsistentExamples"] == ["abc"]
        assert ("inconsistent_types", "age") in {(i["kind"], i.get("column")) for i in a["issues"]}

    def test_mostly_non_numeric_column_is_text(self, df):
        assert {c["name"]: c for c in analyze(df)["columnReports"]}["age"]["type"] == "text"

    def test_whitespace_is_reported(self, df):
        assert ("whitespace", "name") in {(i["kind"], i.get("column")) for i in analyze(df)["issues"]}

    def test_numeric_stats(self, df):
        score = {c["name"]: c for c in analyze(df)["columnReports"]}["score"]
        assert score["stats"]["min"] == 60 and score["stats"]["max"] == 92
        assert score["stats"]["mean"] == pytest.approx((88.5 + 92 + 75 + 75 + 60) / 5, abs=1e-3)

    def test_missing_tokens(self):
        s = pd.Series(["a", "", " ", "NA", "null", "n/a", "-", "0"])
        assert missing_mask(s).tolist() == [False, True, True, True, True, True, True, False]

    def test_type_inference_edge_cases(self):
        assert infer_column(pd.Series(["0", "1", "1"]))["type"] == "integer"
        assert infer_column(pd.Series(["yes", "no", "yes"]))["type"] == "boolean"
        assert infer_column(pd.Series(["1,234", "5,678"]))["type"] == "integer"
        assert infer_column(pd.Series(["hello", "world"]))["type"] == "text"

    def test_perfect_data_scores_high(self):
        d = parse_csv(b"a,b\n1,x\n2,y\n3,z\n")[0]
        a = analyze(d)
        assert a["score"] == 100 and a["issues"] == []


class TestCleaning:
    def test_drop_duplicates_and_trim(self, df):
        out, report = clean(df, CleanOptions(drop_duplicates=True))
        assert len(out) == 5
        assert report["duplicatesRemoved"] == 1 and report["trimmed"] == 1
        assert "Dee" in out["name"].tolist()

    def test_duplicate_subset(self, df):
        out, report = clean(df, CleanOptions(drop_duplicates=True, duplicate_subset=["name"]))
        assert report["duplicatesRemoved"] == 1

    def test_fill_strategies(self):
        d = parse_csv(b"n,c\n1,a\n,a\n3,\n5,b\n")[0]
        out, report = clean(d, CleanOptions(missing={"n": {"strategy": "mean"}, "c": {"strategy": "mode"}}))
        assert out["n"].tolist() == ["1", "3", "3", "5"]
        assert out["c"].tolist() == ["a", "a", "a", "b"]
        assert report["cellsFilled"] == 2
        out2, _ = clean(d, CleanOptions(missing={"n": {"strategy": "constant", "value": "0"}}))
        assert out2["n"].tolist() == ["1", "0", "3", "5"]

    def test_drop_rows_with_missing(self):
        d = parse_csv(b"n,c\n1,a\n,b\n3,c\n")[0]
        out, report = clean(d, CleanOptions(missing={"n": {"strategy": "drop_rows"}}))
        assert len(out) == 2 and report["rowsDroppedForMissing"] == 1

    def test_numeric_fill_on_text_column_is_refused(self):
        d = parse_csv(b"n,c\n1,a\n2,\n")[0]
        with pytest.raises(CleaningError):
            clean(d, CleanOptions(missing={"c": {"strategy": "mean"}}))

    def test_unknown_column_and_missing_constant(self, df):
        with pytest.raises(CleaningError):
            clean(df, CleanOptions(missing={"nope": {"strategy": "mode"}}))
        with pytest.raises(CleaningError):
            clean(df, CleanOptions(missing={"age": {"strategy": "constant"}}))

    def test_input_is_not_mutated(self, df):
        before = df.copy()
        clean(df, CleanOptions(drop_duplicates=True, missing={"score": {"strategy": "median"}}))
        pd.testing.assert_frame_equal(df, before)

    def test_formula_neutralisation(self):
        d = pd.DataFrame({"a": ["=cmd|' /C calc'!A0", "@SUM(1)", "+1+1x", "-5", "normal", "-3.5"]})
        out = neutralize_formulas(d)["a"].tolist()
        assert out[0].startswith("'=") and out[1].startswith("'@") and out[2].startswith("'+")
        assert out[3:] == ["-5", "normal", "-3.5"]


class TestParsing:
    @pytest.mark.parametrize("raw,fragment", [
        (b"", "empty"),
        (b"a,b\n", "no data rows"),
        (b"a,a\n1,2\n", "unique"),
        (b"a,b\n1,2,3\n4,5\n", "malformed"),
        (b"a,b\n\x00\x01\x02,3\n", "binary"),
    ])
    def test_rejects_bad_files(self, raw, fragment):
        with pytest.raises(ValueError, match=fragment):
            parse_csv(raw)

    def test_detects_semicolon_and_latin1(self):
        d, delim = parse_csv("a;b\n1;café\n2;naïve\n".encode("cp1252"))
        assert delim == ";" and d["b"].tolist() == ["café", "naïve"]

    def test_row_limit(self, monkeypatch):
        monkeypatch.setattr(config, "MAX_ROWS", 3)
        with pytest.raises(ValueError, match="Too many rows"):
            parse_csv(b"a\n1\n2\n3\n4\n")


@pytest.fixture
def client():
    return TestClient(app)


def upload(client, content=CSV.encode(), name="people.csv"):
    return client.post("/api/datasets", files={"file": (name, io.BytesIO(content), "text/csv")})


class TestApi:
    def test_upload_clean_download_flow(self, client):
        r = upload(client)
        assert r.status_code == 201
        body = r.json()
        assert body["rows"] == 6 and body["duplicateRows"] == 1
        did = body["id"]

        prev = client.get(f"/api/datasets/{did}/preview?limit=2").json()
        assert prev["total"] == 6 and len(prev["rows"]) == 2

        c = client.post(f"/api/datasets/{did}/clean", json={"dropDuplicates": True, "missing": {"score": {"strategy": "mean"}}})
        assert c.status_code == 200
        assert c.json()["rows"] == 5 and c.json()["duplicateRows"] == 0 and c.json()["cleaned"] is True
        assert c.json()["report"]["duplicatesRemoved"] == 1

        d = client.get(f"/api/datasets/{did}/download")
        assert d.status_code == 200 and d.headers["content-type"].startswith("text/csv")
        assert "people_cleaned.csv" in d.headers["content-disposition"]
        assert len(d.text.strip().splitlines()) == 6  # header + 5 rows

        assert client.get(f"/api/datasets/{did}/download?version=original").text.count("\n") >= 7
        assert client.post(f"/api/datasets/{did}/reset").json()["cleaned"] is False
        assert client.get(f"/api/datasets/{did}/download").status_code == 404
        assert client.delete(f"/api/datasets/{did}").status_code == 204
        assert client.get(f"/api/datasets/{did}").status_code == 404

    def test_cleaning_options_do_not_compound(self, client):
        did = upload(client).json()["id"]
        client.post(f"/api/datasets/{did}/clean", json={"dropDuplicates": True})
        again = client.post(f"/api/datasets/{did}/clean", json={"dropDuplicates": False}).json()
        assert again["rows"] == 6

    def test_rejects_wrong_extension_and_oversize(self, client, monkeypatch):
        assert upload(client, name="data.exe").status_code == 415
        monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 100)
        assert upload(client, b"a,b\n" + b"1,2\n" * 100).status_code == 413

    def test_malformed_and_binary_files_give_clear_errors(self, client):
        r = upload(client, b"a,b\n1,2,3\n4,5\n")
        assert r.status_code == 422 and "malformed" in r.json()["detail"]
        assert upload(client, b"\x89PNG\r\n\x1a\n\x00\x00", name="x.csv").status_code == 422

    def test_ids_are_validated_and_unknown_is_404(self, client):
        for bad in ["../../etc/passwd", "zzz", "0" * 32]:
            assert client.get(f"/api/datasets/{bad}").status_code == 404

    def test_invalid_cleaning_request_is_422(self, client):
        did = upload(client).json()["id"]
        r = client.post(f"/api/datasets/{did}/clean", json={"missing": {"age": {"strategy": "mean"}}})
        assert r.status_code == 422

    def test_expired_datasets_are_swept(self, client):
        did = upload(client).json()["id"]
        import time
        assert store.sweep(now=time.time() + config.TTL_SECONDS + 5) == 1
        assert client.get(f"/api/datasets/{did}").status_code == 404

    def test_dataset_cap_evicts_oldest(self, client, monkeypatch):
        monkeypatch.setattr(config, "MAX_DATASETS", 2)
        ids = [upload(client).json()["id"] for _ in range(4)]
        alive = [i for i in ids if client.get(f"/api/datasets/{i}").status_code == 200]
        assert len(alive) <= 3 and ids[-1] in alive
