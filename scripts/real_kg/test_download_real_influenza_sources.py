"""Mocked-network tests for real influenza source ingestion."""

import argparse
import csv
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scripts.real_kg.download_real_influenza_sources import (
    INVENTORY_COLUMNS,
    build_socrata_sample_url,
    epiweek_date_window,
    fetch_delphi_source,
    fetch_json,
    fetch_socrata_metadata,
    fetch_socrata_sample,
    ingest_sources,
    inventory_row,
    write_inventory,
)


class FakeResponse:
    def __init__(self, payload=None, raw=None):
        self.raw = (
            raw
            if raw is not None
            else json.dumps(payload).encode("utf-8")
        )

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def read(self):
        return self.raw


class DownloadRealInfluenzaSourcesTests(unittest.TestCase):
    def test_epiweek_date_window_includes_seven_day_buffers(self):
        start_date, end_date = epiweek_date_window(202440, 202520)

        self.assertEqual(start_date, date(2024, 9, 23))
        self.assertEqual(end_date, date(2025, 5, 25))

    def test_socrata_metadata_fetch_parsing(self):
        payload = {
            "id": "vdzy-6i9v",
            "name": "Hospital admissions",
            "columns": [{"fieldName": "week"}, {"fieldName": "value"}],
        }
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ) as urlopen:
            metadata = fetch_socrata_metadata(
                "vdzy-6i9v",
                "cdc_hospital_respiratory_admissions",
            )

        self.assertEqual(metadata["id"], "vdzy-6i9v")
        self.assertEqual(len(metadata["columns"]), 2)
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://data.cdc.gov/api/views/vdzy-6i9v",
        )

    def test_socrata_sample_row_fetch_parsing(self):
        payload = [
            {"week": "2025-W01", "value": "1.2"},
            {"week": "2025-W02", "value": "1.5"},
        ]
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ) as urlopen:
            rows = fetch_socrata_sample(
                "ymmh-divb",
                "cdc_influenza_a_wastewater",
                25,
            )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["week"], "2025-W01")
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://data.cdc.gov/resource/ymmh-divb.json?$limit=25",
        )

    def test_hospital_sample_url_includes_date_filter_and_order(self):
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse([]),
        ) as urlopen:
            fetch_socrata_sample(
                "vdzy-6i9v",
                "cdc_hospital_respiratory_admissions",
                5000,
                date_column="weekendingdate",
                start_date=date(2024, 9, 23),
                end_date=date(2025, 5, 25),
                order="weekendingdate,jurisdiction",
            )

        request = urlopen.call_args.args[0]
        query = urllib.parse.parse_qs(
            urllib.parse.urlparse(request.full_url).query
        )
        self.assertEqual(query["$limit"], ["5000"])
        self.assertEqual(
            query["$where"],
            [
                "weekendingdate >= '2024-09-23T00:00:00' AND "
                "weekendingdate <= '2025-05-25T23:59:59'"
            ],
        )
        self.assertEqual(
            query["$order"],
            ["weekendingdate,jurisdiction"],
        )

    def test_wastewater_sample_url_includes_date_filter_and_order(self):
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse([]),
        ) as urlopen:
            fetch_socrata_sample(
                "ymmh-divb",
                "cdc_influenza_a_wastewater",
                5000,
                date_column="sample_collect_date",
                start_date=date(2024, 9, 23),
                end_date=date(2025, 5, 25),
                order="sample_collect_date,state_territory,site",
            )

        request = urlopen.call_args.args[0]
        query = urllib.parse.parse_qs(
            urllib.parse.urlparse(request.full_url).query
        )
        self.assertEqual(
            query["$where"],
            [
                "sample_collect_date >= '2024-09-23T00:00:00' AND "
                "sample_collect_date <= '2025-05-25T23:59:59'"
            ],
        )
        self.assertEqual(
            query["$order"],
            ["sample_collect_date,state_territory,site"],
        )

    def test_disable_date_filter_uses_legacy_limit_only_url(self):
        url = build_socrata_sample_url(
            dataset_id="vdzy-6i9v",
            limit=123,
        )
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)

        self.assertEqual(query, {"$limit": ["123"]})
        self.assertNotIn("$where", query)
        self.assertNotIn("$order", query)

    def test_disable_date_filter_is_applied_by_ingestion(self):
        metadata = {"columns": [{"fieldName": "week"}]}
        delphi = {
            "result": 1,
            "message": "success",
            "epidata": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            args = argparse.Namespace(
                start_epiweek=202440,
                end_epiweek=202520,
                socrata_limit=20,
                output_dir=temp_path / "raw",
                inventory_output=temp_path / "inventory.csv",
                metadata_only=False,
                disable_socrata_date_filter=True,
            )
            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(metadata),
                    FakeResponse([]),
                    FakeResponse(metadata),
                    FakeResponse([]),
                    FakeResponse(delphi),
                    FakeResponse(delphi),
                ],
            ) as urlopen:
                inventory = ingest_sources(args)

        sample_urls = [
            call.args[0].full_url
            for call in (
                urlopen.call_args_list[1],
                urlopen.call_args_list[3],
            )
        ]
        for url in sample_urls:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            self.assertEqual(query, {"$limit": ["20"]})
            self.assertNotIn("$where", query)
        socrata_notes = [
            row["notes"]
            for row in inventory
            if row["source_type"] == "socrata"
        ]
        self.assertTrue(
            all("date filter disabled" in note for note in socrata_notes)
        )

    def test_delphi_fluview_response_parsing(self):
        payload = {
            "result": 1,
            "message": "success",
            "epidata": [{"region": "nat", "epiweek": 202440, "wili": 2.1}],
        }
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ) as urlopen:
            response, rows = fetch_delphi_source(
                "fluview",
                "delphi_fluview_ili",
                202440,
                202520,
            )

        self.assertEqual(response["result"], 1)
        self.assertEqual(rows[0]["wili"], 2.1)
        request = urlopen.call_args.args[0]
        self.assertIn("/epidata/fluview/", request.full_url)
        self.assertIn("regions=nat", request.full_url)
        self.assertIn("epiweeks=202440-202520", request.full_url)

    def test_delphi_fluview_clinical_response_parsing(self):
        payload = {
            "result": 1,
            "message": "success",
            "epidata": [
                {
                    "region": "nat",
                    "epiweek": 202440,
                    "total_specimens": 1000,
                    "total_positive": 120,
                }
            ],
        }
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ) as urlopen:
            _response, rows = fetch_delphi_source(
                "fluview_clinical",
                "delphi_fluview_clinical",
                202440,
                202520,
            )

        self.assertEqual(rows[0]["total_positive"], 120)
        request = urlopen.call_args.args[0]
        self.assertIn("/epidata/fluview_clinical/", request.full_url)

    def test_inventory_csv_writing(self):
        row = inventory_row(
            source_name="test_source",
            source_type="socrata",
            dataset_id_or_endpoint="abcd-1234",
            intended_signal_role="test role",
            raw_output_path=Path("raw/test.json"),
            rows=[{"week": 1, "value": 2}],
            columns=["value", "week"],
            time_range_requested="",
            date_accessed_utc="2026-07-01T00:00:00+00:00",
            notes="Test inventory row.",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "inventory.csv"
            write_inventory(path, [row])
            with path.open("r", newline="", encoding="utf-8") as input_file:
                reader = csv.DictReader(input_file)
                rows = list(reader)

        self.assertEqual(reader.fieldnames, INVENTORY_COLUMNS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["row_count"], "1")
        self.assertEqual(rows[0]["column_count"], "2")

    def test_metadata_only_skips_all_sample_row_downloads(self):
        metadata = {
            "columns": [{"fieldName": "week"}, {"fieldName": "value"}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            args = argparse.Namespace(
                start_epiweek=202440,
                end_epiweek=202520,
                socrata_limit=5000,
                output_dir=temp_path / "raw",
                inventory_output=temp_path / "inventory.csv",
                metadata_only=True,
                disable_socrata_date_filter=False,
            )
            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(metadata),
                    FakeResponse(metadata),
                ],
            ) as urlopen:
                inventory = ingest_sources(args)

            requested_urls = [
                call.args[0].full_url for call in urlopen.call_args_list
            ]
            self.assertEqual(urlopen.call_count, 2)
            self.assertTrue(
                all("/api/views/" in url for url in requested_urls)
            )
            self.assertFalse(
                any("/resource/" in url for url in requested_urls)
            )
            self.assertFalse(
                any("api.delphi" in url for url in requested_urls)
            )
            self.assertEqual(len(inventory), 4)
            self.assertTrue(args.inventory_output.is_file())
            self.assertFalse(
                (
                    args.output_dir
                    / "cdc_hospital_respiratory_admissions_sample.json"
                ).exists()
            )

    def test_inventory_notes_include_applied_date_filter(self):
        metadata = {
            "columns": [{"fieldName": "week"}, {"fieldName": "value"}],
        }
        delphi = {
            "result": 1,
            "message": "success",
            "epidata": [{"region": "nat", "epiweek": 202440, "value": 1}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            args = argparse.Namespace(
                start_epiweek=202440,
                end_epiweek=202520,
                socrata_limit=5000,
                output_dir=temp_path / "raw",
                inventory_output=temp_path / "inventory.csv",
                metadata_only=False,
                disable_socrata_date_filter=False,
            )
            with patch(
                "urllib.request.urlopen",
                side_effect=[
                    FakeResponse(metadata),
                    FakeResponse([{"week": "2025-01-01"}]),
                    FakeResponse(metadata),
                    FakeResponse([{"week": "2025-01-01"}]),
                    FakeResponse(delphi),
                    FakeResponse(delphi),
                ],
            ):
                inventory = ingest_sources(args)

        hospital = next(
            row
            for row in inventory
            if row["source_name"]
            == "cdc_hospital_respiratory_admissions"
        )
        wastewater = next(
            row
            for row in inventory
            if row["source_name"] == "cdc_influenza_a_wastewater"
        )
        self.assertIn(
            "Applied date filter on weekendingdate: "
            "2024-09-23 through 2025-05-25",
            hospital["notes"],
        )
        self.assertIn(
            "Applied date filter on sample_collect_date: "
            "2024-09-23 through 2025-05-25",
            wastewater["notes"],
        )

    def test_http_and_json_failures_are_helpful(self):
        http_error = urllib.error.HTTPError(
            url="https://example.test/source",
            code=503,
            msg="Unavailable",
            hdrs=None,
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaisesRegex(
                RuntimeError,
                "HTTP 503.*test_source",
            ):
                fetch_json("https://example.test/source", "test_source")

        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(raw=b"not-json"),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Invalid JSON.*test_source",
            ):
                fetch_json("https://example.test/source", "test_source")

    def test_delphi_result_code_failure_is_helpful(self):
        payload = {
            "result": -2,
            "message": "no results",
            "epidata": [],
        }
        with patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ):
            with self.assertRaisesRegex(
                ValueError,
                "result code -2.*no results",
            ):
                fetch_delphi_source(
                    "fluview",
                    "delphi_fluview_ili",
                    202440,
                    202520,
                )


if __name__ == "__main__":
    unittest.main()
