"""
Tests for the ADA Bridge app.

- Unit tests for translator_ada.py (JSON-LD -> ADA field mapping)
- Unit tests for bundle_service.py (ZIP introspection)
- Integration tests for push/sync flow (mocked ADA API)
"""

import hashlib
import io
import json
import os
import tempfile
import uuid
import zipfile
from datetime import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ada_bridge.bundle_service import introspect_bundle
from ada_bridge.models import AdaRecordLink
from ada_bridge.translator_ada import (
    _get,
    _strip_prefix,
    _translate_contributors,
    _translate_creators,
    _translate_files,
    _translate_funding,
    _translate_licenses,
    _translate_subjects,
    ada_to_jsonld_status,
    compute_payload_checksum,
    jsonld_to_ada,
)
from records.models import Profile, Record

User = get_user_model()


# ---------------------------------------------------------------------------
# Sample JSON-LD fixtures
# ---------------------------------------------------------------------------

FULL_JSONLD = {
    "@context": {"schema": "http://schema.org/"},
    "@type": ["schema:Dataset"],
    "@id": "https://doi.org/10.1234/test",
    "schema:name": "Test Dataset Title",
    "schema:description": "A test description for the dataset.",
    "schema:datePublished": "2026-01-15",
    "schema:additionalType": "Geochemistry",
    "submissionType": "Regular",
    "schema:creator": {
        "@list": [
            {
                "@type": "schema:Person",
                "schema:name": "Alice Smith",
                "schema:givenName": "Alice",
                "schema:familyName": "Smith",
                "schema:identifier": "0000-0001-2345-6789",
            },
            {
                "@type": "schema:Organization",
                "schema:name": "IEDA",
            },
        ]
    },
    "schema:contributor": [
        {
            "@type": "schema:Person",
            "schema:name": "Bob Jones",
            "schema:identifier": "0000-0002-3456-7890",
        }
    ],
    "schema:funding": [
        {
            "funder": {
                "@type": "schema:Organization",
                "schema:name": "NSF",
            },
            "identifier": "EAR-1234567",
            "name": "Geochemistry of Bennu",
        }
    ],
    "schema:license": [
        {"schema:name": "CC-BY-4.0", "schema:url": "https://creativecommons.org/licenses/by/4.0/"},
    ],
    "schema:distribution": [
        {
            "schema:name": "data.csv",
            "schema:encodingFormat": "text/csv",
        },
        {
            "schema:description": "Image file",
            "schema:encodingFormat": "image/tiff",
        },
    ],
}

MINIMAL_JSONLD = {
    "schema:name": "Minimal Record",
}

EMPTY_CREATOR_JSONLD = {
    "schema:name": "No Creators",
    "schema:creator": {"@list": []},
}


# ===================================================================
# translator_ada.py — Unit Tests
# ===================================================================


class StripPrefixTest(TestCase):
    def test_strips_schema_prefix(self):
        self.assertEqual(_strip_prefix("schema:name"), "name")

    def test_strips_arbitrary_prefix(self):
        self.assertEqual(_strip_prefix("dc:title"), "title")

    def test_no_prefix(self):
        self.assertEqual(_strip_prefix("name"), "name")

    def test_at_prefix_preserved(self):
        self.assertEqual(_strip_prefix("@type"), "@type")

    def test_empty_string(self):
        self.assertEqual(_strip_prefix(""), "")


class GetHelperTest(TestCase):
    def test_finds_prefixed_key(self):
        obj = {"schema:name": "Test"}
        self.assertEqual(_get(obj, "schema:name"), "Test")

    def test_finds_bare_key(self):
        obj = {"name": "Test"}
        self.assertEqual(_get(obj, "schema:name"), "Test")

    def test_prefers_prefixed_over_bare(self):
        obj = {"schema:name": "Prefixed", "name": "Bare"}
        self.assertEqual(_get(obj, "schema:name"), "Prefixed")

    def test_returns_default(self):
        self.assertEqual(_get({}, "schema:name", "default"), "default")

    def test_returns_none_by_default(self):
        self.assertIsNone(_get({}, "schema:name"))


class TranslateCreatorsTest(TestCase):
    def test_person_creator(self):
        creators = _translate_creators(FULL_JSONLD)
        self.assertEqual(len(creators), 2)
        alice = creators[0]
        self.assertEqual(alice["nameEntity"]["fullName"], "Alice Smith")
        self.assertEqual(alice["nameEntity"]["givenName"], "Alice")
        self.assertEqual(alice["nameEntity"]["familyName"], "Smith")
        self.assertEqual(alice["nameEntity"]["nameType"], "Personal")

    def test_organization_creator(self):
        creators = _translate_creators(FULL_JSONLD)
        ieda = creators[1]
        self.assertEqual(ieda["nameEntity"]["fullName"], "IEDA")
        self.assertEqual(ieda["nameEntity"]["nameType"], "Organizational")

    def test_orcid_string_identifier(self):
        creators = _translate_creators(FULL_JSONLD)
        self.assertEqual(creators[0]["nameEntity"]["orcid"], "0000-0001-2345-6789")

    def test_orcid_dict_identifier(self):
        jsonld = {
            "schema:creator": {
                "@list": [
                    {
                        "@type": "schema:Person",
                        "schema:name": "Jane Doe",
                        "schema:identifier": {
                            "schema:value": "0000-0003-9999-0001",
                        },
                    }
                ]
            }
        }
        creators = _translate_creators(jsonld)
        self.assertEqual(creators[0]["nameEntity"]["orcid"], "0000-0003-9999-0001")

    def test_orcid_dict_with_url_fallback(self):
        jsonld = {
            "schema:creator": [
                {
                    "@type": "schema:Person",
                    "schema:name": "Jane Doe",
                    "schema:identifier": {
                        "schema:url": "https://orcid.org/0000-0003-9999-0002",
                    },
                }
            ]
        }
        creators = _translate_creators(jsonld)
        self.assertEqual(creators[0]["nameEntity"]["orcid"], "https://orcid.org/0000-0003-9999-0002")

    def test_auto_split_full_name(self):
        jsonld = {
            "schema:creator": [
                {"@type": "schema:Person", "schema:name": "John Doe"}
            ]
        }
        creators = _translate_creators(jsonld)
        self.assertEqual(creators[0]["nameEntity"]["givenName"], "John")
        self.assertEqual(creators[0]["nameEntity"]["familyName"], "Doe")

    def test_single_word_name(self):
        jsonld = {
            "schema:creator": [
                {"@type": "schema:Person", "schema:name": "Madonna"}
            ]
        }
        creators = _translate_creators(jsonld)
        self.assertEqual(creators[0]["nameEntity"]["givenName"], "")
        self.assertEqual(creators[0]["nameEntity"]["familyName"], "Madonna")

    def test_empty_creator_list(self):
        creators = _translate_creators(EMPTY_CREATOR_JSONLD)
        self.assertEqual(creators, [])

    def test_no_creator_key(self):
        creators = _translate_creators({"schema:name": "No creators"})
        self.assertEqual(creators, [])

    def test_flat_list_creators(self):
        jsonld = {
            "schema:creator": [
                {"@type": "schema:Person", "schema:name": "Flat Creator"}
            ]
        }
        creators = _translate_creators(jsonld)
        self.assertEqual(len(creators), 1)
        self.assertEqual(creators[0]["nameEntity"]["fullName"], "Flat Creator")

    def test_type_as_list(self):
        jsonld = {
            "schema:creator": [
                {"@type": ["schema:Person", "schema:Thing"], "schema:name": "Multi Type"}
            ]
        }
        creators = _translate_creators(jsonld)
        self.assertEqual(creators[0]["nameEntity"]["nameType"], "Personal")


class TranslateContributorsTest(TestCase):
    def test_basic_contributor(self):
        contributors = _translate_contributors(FULL_JSONLD)
        self.assertEqual(len(contributors), 1)
        bob = contributors[0]
        self.assertEqual(bob["nameEntity"]["fullName"], "Bob Jones")
        self.assertEqual(bob["nameEntity"]["nameType"], "Personal")
        self.assertEqual(bob["nameEntity"]["orcid"], "0000-0002-3456-7890")

    def test_role_contributor(self):
        jsonld = {
            "schema:contributor": [
                {
                    "@type": "schema:Role",
                    "roleName": "Data Collector",
                    "contributor": {
                        "@type": "schema:Person",
                        "schema:name": "Role Person",
                    },
                }
            ]
        }
        contributors = _translate_contributors(jsonld)
        self.assertEqual(len(contributors), 1)
        self.assertEqual(contributors[0]["contributorType"], "Data Collector")
        self.assertEqual(contributors[0]["nameEntity"]["fullName"], "Role Person")

    def test_no_contributors(self):
        contributors = _translate_contributors({"schema:name": "No contribs"})
        self.assertEqual(contributors, [])

    def test_empty_contributors(self):
        contributors = _translate_contributors({"schema:contributor": []})
        self.assertEqual(contributors, [])


class TranslateFundingTest(TestCase):
    def test_basic_funding(self):
        funding = _translate_funding(FULL_JSONLD)
        self.assertEqual(len(funding), 1)
        entry = funding[0]
        self.assertEqual(entry["funder"]["name"], "NSF")
        self.assertEqual(entry["awardNumber"], "EAR-1234567")
        self.assertEqual(entry["awardTitle"], "Geochemistry of Bennu")

    def test_string_funder(self):
        jsonld = {
            "schema:funding": [
                {"funder": "DOE", "identifier": "DE-123", "name": "Energy Grant"}
            ]
        }
        funding = _translate_funding(jsonld)
        self.assertEqual(funding[0]["funder"]["name"], "DOE")

    def test_no_funding(self):
        funding = _translate_funding({"schema:name": "No funding"})
        self.assertEqual(funding, [])


class TranslateLicensesTest(TestCase):
    def test_license_dict(self):
        licenses = _translate_licenses(FULL_JSONLD)
        self.assertEqual(len(licenses), 1)
        self.assertEqual(licenses[0]["name"], "CC-BY-4.0")
        self.assertEqual(licenses[0]["url"], "https://creativecommons.org/licenses/by/4.0/")

    def test_license_string(self):
        jsonld = {"schema:license": ["MIT"]}
        licenses = _translate_licenses(jsonld)
        self.assertEqual(licenses, [{"name": "MIT"}])

    def test_single_license_string(self):
        jsonld = {"schema:license": "Apache-2.0"}
        licenses = _translate_licenses(jsonld)
        self.assertEqual(licenses, [{"name": "Apache-2.0"}])

    def test_no_licenses(self):
        licenses = _translate_licenses({})
        self.assertEqual(licenses, [])


class TranslateFilesTest(TestCase):
    def test_files(self):
        files = _translate_files(FULL_JSONLD)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]["name"], "data.csv")
        self.assertEqual(files[0]["extension"], "text/csv")

    def test_file_uses_description_as_name_fallback(self):
        files = _translate_files(FULL_JSONLD)
        self.assertEqual(files[1]["name"], "Image file")

    def test_no_files(self):
        files = _translate_files({})
        self.assertEqual(files, [])


class TranslateSubjectsTest(TestCase):
    def test_subjects_from_about(self):
        jsonld = {
            "schema:about": [
                {"name": "Geochemistry", "scheme": "GCMD"},
            ]
        }
        subjects = _translate_subjects(jsonld, "adaProduct")
        self.assertEqual(len(subjects), 1)

    def test_no_subjects(self):
        subjects = _translate_subjects({}, "adaProduct")
        self.assertEqual(subjects, [])


class JsonldToAdaTest(TestCase):
    def test_full_translation(self):
        payload = jsonld_to_ada(FULL_JSONLD, profile="adaProduct")
        self.assertEqual(payload["title"], "Test Dataset Title")
        self.assertEqual(payload["description"], "A test description for the dataset.")
        self.assertEqual(payload["publicationDate"], "2026-01-15")
        self.assertEqual(payload["specificType"], "Geochemistry")
        self.assertEqual(payload["submissionType"], "Regular")
        self.assertIn("creators", payload)
        self.assertIn("contributors", payload)
        self.assertIn("funding", payload)
        self.assertIn("licenses", payload)
        self.assertIn("files", payload)

    def test_minimal_translation(self):
        payload = jsonld_to_ada(MINIMAL_JSONLD)
        self.assertEqual(payload["title"], "Minimal Record")
        self.assertEqual(payload["description"], "")
        self.assertNotIn("creators", payload)
        self.assertNotIn("publicationDate", payload)

    def test_empty_arrays_excluded(self):
        payload = jsonld_to_ada(EMPTY_CREATOR_JSONLD)
        self.assertNotIn("creators", payload)

    def test_additional_type_list(self):
        jsonld = {"schema:name": "Test", "schema:additionalType": ["Type1", "Type2"]}
        payload = jsonld_to_ada(jsonld)
        self.assertEqual(payload["specificType"], "Type1")


class AdaToJsonldStatusTest(TestCase):
    def test_writes_status_camel_case(self):
        link = mock.MagicMock()
        ada_to_jsonld_status({"processStatus": "Pending", "doi": "10.1234/test"}, link)
        self.assertEqual(link.ada_status, "Pending")
        self.assertEqual(link.ada_doi, "10.1234/test")

    def test_writes_status_snake_case(self):
        link = mock.MagicMock()
        ada_to_jsonld_status({"process_status": "Published"}, link)
        self.assertEqual(link.ada_status, "Published")

    def test_empty_doi_not_overwritten(self):
        link = mock.MagicMock()
        link.ada_doi = "existing"
        ada_to_jsonld_status({"processStatus": "Pending"}, link)
        # ada_doi should not be overwritten when doi is empty/missing
        self.assertEqual(link.ada_doi, "existing")


class ComputePayloadChecksumTest(TestCase):
    def test_deterministic(self):
        payload = {"title": "Test", "description": "Desc"}
        c1 = compute_payload_checksum(payload)
        c2 = compute_payload_checksum(payload)
        self.assertEqual(c1, c2)

    def test_key_order_independent(self):
        p1 = {"b": 2, "a": 1}
        p2 = {"a": 1, "b": 2}
        self.assertEqual(compute_payload_checksum(p1), compute_payload_checksum(p2))

    def test_different_payloads(self):
        p1 = {"title": "A"}
        p2 = {"title": "B"}
        self.assertNotEqual(compute_payload_checksum(p1), compute_payload_checksum(p2))

    def test_returns_hex_sha256(self):
        checksum = compute_payload_checksum({"key": "val"})
        self.assertEqual(len(checksum), 64)
        # Verify it's valid hex
        int(checksum, 16)


# ===================================================================
# bundle_service.py — Unit Tests
# ===================================================================


class BundleIntrospectionTest(TestCase):
    def _create_zip(self, files: dict) -> str:
        """Create a temp ZIP with given {name: content} mapping."""
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(tmp, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        tmp.close()
        return tmp.name

    def test_introspect_valid_zip(self):
        path = self._create_zip({"data.csv": "a,b,c\n1,2,3\n", "readme.txt": "Hello"})
        try:
            result = introspect_bundle(path)
            self.assertIn("manifest", result)
            self.assertIn("data.csv", result["manifest"])
            self.assertIn("readme.txt", result["manifest"])
            self.assertIsInstance(result["files"], dict)
            self.assertIsInstance(result["warnings"], list)
        finally:
            os.unlink(path)

    def test_introspect_not_a_zip(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.write(b"This is not a zip file")
        tmp.close()
        try:
            result = introspect_bundle(tmp.name)
            self.assertEqual(result["manifest"], [])
            self.assertIn("not a valid ZIP archive", result["warnings"][0])
        finally:
            os.unlink(tmp.name)

    def test_introspect_skips_directories(self):
        path = self._create_zip({"folder/file.txt": "content"})
        try:
            result = introspect_bundle(path)
            # Should have the file but not a bare directory entry
            self.assertIn("folder/file.txt", result["manifest"])
        finally:
            os.unlink(path)

    def test_introspect_csv_produces_no_warnings(self):
        """A simple CSV is inspected successfully with no warnings."""
        path = self._create_zip({"data.csv": "a,b\n1,2\n"})
        try:
            result = introspect_bundle(path)
            self.assertEqual(result["warnings"], [])
            self.assertIn("data.csv", result["files"])
        finally:
            os.unlink(path)

    def test_introspect_empty_zip(self):
        path = self._create_zip({})
        try:
            result = introspect_bundle(path)
            self.assertEqual(result["manifest"], [])
        finally:
            os.unlink(path)


# ===================================================================
# Integration tests — Push / Sync / Status views (mocked ADA API)
# ===================================================================


ADA_CREATE_RESPONSE = {
    "id": 42,
    "doi": "10.82622/dev-test123",
    "processStatus": "Pending",
    "title": "Test Dataset Title",
}

ADA_GET_RESPONSE = {
    "id": 42,
    "doi": "10.82622/dev-test123",
    "processStatus": "Published",
    "title": "Test Dataset Title",
}

ADA_UPDATE_RESPONSE = {
    "id": 42,
    "doi": "10.82622/dev-test123",
    "processStatus": "Pending",
    "title": "Updated Title",
}


class PushViewIntegrationTest(TestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL (Record model uses ArrayField/GinIndex)")
        self.user = User.objects.create_user(
            username="testuser", password="testpass", orcid="0000-0000-0000-0099"
        )
        self.profile = Profile.objects.create(name="adaProduct", schema={})
        self.record = Record.objects.create(
            profile=self.profile,
            jsonld=FULL_JSONLD,
            owner=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @mock.patch("ada_bridge.services.AdaClient")
    def test_push_creates_link(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.create_record.return_value = ADA_CREATE_RESPONSE

        resp = self.client.post(f"/api/ada-bridge/push/{self.record.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["ada_record_id"], 42)
        self.assertEqual(resp.json()["ada_doi"], "10.82622/dev-test123")
        self.assertEqual(resp.json()["ada_status"], "Pending")

        # Verify link was created in DB
        link = AdaRecordLink.objects.get(ieda_record=self.record)
        self.assertEqual(link.ada_record_id, 42)
        self.assertEqual(link.ada_doi, "10.82622/dev-test123")
        self.assertIsNotNone(link.last_pushed_at)
        self.assertTrue(len(link.push_checksum) == 64)

    @mock.patch("ada_bridge.services.AdaClient")
    def test_push_skips_unchanged(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.create_record.return_value = ADA_CREATE_RESPONSE

        # First push
        self.client.post(f"/api/ada-bridge/push/{self.record.id}/")
        first_pushed_at = AdaRecordLink.objects.get(ieda_record=self.record).last_pushed_at

        # Second push — should skip (same checksum)
        resp = self.client.post(f"/api/ada-bridge/push/{self.record.id}/")
        self.assertEqual(resp.status_code, 200)
        second_pushed_at = AdaRecordLink.objects.get(ieda_record=self.record).last_pushed_at
        self.assertEqual(first_pushed_at, second_pushed_at)

        # create_record should only have been called once
        mock_client.create_record.assert_called_once()

    @mock.patch("ada_bridge.services.AdaClient")
    def test_push_updates_after_metadata_change(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.create_record.return_value = ADA_CREATE_RESPONSE
        mock_client.update_record.return_value = ADA_UPDATE_RESPONSE

        # First push
        self.client.post(f"/api/ada-bridge/push/{self.record.id}/")

        # Modify the record metadata
        new_jsonld = dict(FULL_JSONLD)
        new_jsonld["schema:name"] = "Updated Title"
        self.record.jsonld = new_jsonld
        self.record.save()

        # Second push — should call update
        resp = self.client.post(f"/api/ada-bridge/push/{self.record.id}/")
        self.assertEqual(resp.status_code, 200)
        mock_client.update_record.assert_called_once()

    def test_push_nonexistent_record(self):
        fake_id = uuid.uuid4()
        resp = self.client.post(f"/api/ada-bridge/push/{fake_id}/")
        self.assertEqual(resp.status_code, 404)

    @mock.patch("ada_bridge.services.AdaClient")
    def test_push_ada_error(self, MockClient):
        from ada_bridge.client import AdaClientError
        mock_client = MockClient.return_value
        mock_client.create_record.side_effect = AdaClientError(500, "Internal Error")

        resp = self.client.post(f"/api/ada-bridge/push/{self.record.id}/")
        self.assertEqual(resp.status_code, 502)
        self.assertIn("ADA API error", resp.json()["detail"])

    def test_push_requires_auth(self):
        self.client.logout()
        resp = self.client.post(f"/api/ada-bridge/push/{self.record.id}/")
        self.assertIn(resp.status_code, [401, 403])


class SyncViewIntegrationTest(TestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL (Record model uses ArrayField/GinIndex)")
        self.user = User.objects.create_user(
            username="testuser", password="testpass", orcid="0000-0000-0000-0099"
        )
        self.profile = Profile.objects.create(name="adaProduct", schema={})
        self.record = Record.objects.create(
            profile=self.profile,
            jsonld=FULL_JSONLD,
            owner=self.user,
        )
        self.link = AdaRecordLink.objects.create(
            ieda_record=self.record,
            ada_record_id=42,
            ada_doi="10.82622/dev-test123",
            ada_status="Pending",
            last_pushed_at=timezone.now(),
            push_checksum="abc123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @mock.patch("ada_bridge.services.AdaClient")
    def test_sync_updates_status(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.get_record_status.return_value = ADA_GET_RESPONSE

        resp = self.client.post(f"/api/ada-bridge/sync/{self.record.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["ada_status"], "Published")
        self.assertIn("synced_at", resp.json())

        # Verify DB updated
        self.link.refresh_from_db()
        self.assertEqual(self.link.ada_status, "Published")
        self.assertIsNotNone(self.link.last_synced_at)

    def test_sync_without_link(self):
        # Delete the link
        self.link.delete()

        resp = self.client.post(f"/api/ada-bridge/sync/{self.record.id}/")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("No ADA link", resp.json()["detail"])

    def test_sync_requires_auth(self):
        self.client.logout()
        resp = self.client.post(f"/api/ada-bridge/sync/{self.record.id}/")
        self.assertIn(resp.status_code, [401, 403])


class StatusViewIntegrationTest(TestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL (Record model uses ArrayField/GinIndex)")
        self.user = User.objects.create_user(
            username="testuser", password="testpass", orcid="0000-0000-0000-0099"
        )
        self.profile = Profile.objects.create(name="adaProduct", schema={})
        self.record = Record.objects.create(
            profile=self.profile,
            jsonld=FULL_JSONLD,
            owner=self.user,
        )
        self.link = AdaRecordLink.objects.create(
            ieda_record=self.record,
            ada_record_id=42,
            ada_doi="10.82622/dev-test123",
            ada_status="Pending",
            last_pushed_at=timezone.now(),
            push_checksum="abc123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_status_returns_link_data(self):
        resp = self.client.get(f"/api/ada-bridge/status/{self.record.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ada_record_id"], 42)
        self.assertEqual(data["ada_doi"], "10.82622/dev-test123")
        self.assertEqual(data["ada_status"], "Pending")
        self.assertEqual(data["ieda_record_id"], str(self.record.id))
        self.assertIn("push_checksum", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_status_without_link(self):
        self.link.delete()
        resp = self.client.get(f"/api/ada-bridge/status/{self.record.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_status_requires_auth(self):
        self.client.logout()
        resp = self.client.get(f"/api/ada-bridge/status/{self.record.id}/")
        self.assertIn(resp.status_code, [401, 403])


class BundleIntrospectViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass", orcid="0000-0000-0000-0099"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_introspect_upload(self):
        # Create a simple zip in memory
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("sample.csv", "a,b\n1,2\n")
        buf.seek(0)
        buf.name = "test.zip"

        resp = self.client.post(
            "/api/ada-bridge/bundle/introspect/",
            {"file": buf},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("manifest", data)
        self.assertIn("sample.csv", data["manifest"])

    def test_introspect_requires_file(self):
        resp = self.client.post("/api/ada-bridge/bundle/introspect/", {}, format="multipart")
        self.assertEqual(resp.status_code, 400)

    def test_introspect_requires_auth(self):
        self.client.logout()
        resp = self.client.post("/api/ada-bridge/bundle/introspect/", {}, format="multipart")
        self.assertIn(resp.status_code, [401, 403])


class TranslatorPayloadFormatTest(TestCase):
    """Ensure the translator output uses camelCase keys for ADA's CamelCaseJSONParser."""

    def test_creator_keys_are_camel_case(self):
        payload = jsonld_to_ada(FULL_JSONLD)
        creator = payload["creators"][0]
        self.assertIn("nameEntity", creator)
        ne = creator["nameEntity"]
        self.assertIn("fullName", ne)
        self.assertIn("givenName", ne)
        self.assertIn("familyName", ne)
        self.assertIn("nameType", ne)

    def test_contributor_type_is_camel_case(self):
        jsonld = {
            "schema:contributor": [
                {
                    "@type": "schema:Role",
                    "roleName": "Data Collector",
                    "contributor": {
                        "@type": "schema:Person",
                        "schema:name": "Test Person",
                    },
                }
            ]
        }
        payload = jsonld_to_ada(jsonld)
        self.assertIn("contributorType", payload["contributors"][0])

    def test_funding_keys_are_camel_case(self):
        payload = jsonld_to_ada(FULL_JSONLD)
        fund = payload["funding"][0]
        self.assertIn("awardNumber", fund)
        self.assertIn("awardTitle", fund)

    def test_publication_date_is_camel_case(self):
        payload = jsonld_to_ada(FULL_JSONLD)
        self.assertIn("publicationDate", payload)

    def test_submission_type_is_camel_case(self):
        payload = jsonld_to_ada(FULL_JSONLD)
        self.assertIn("submissionType", payload)

    def test_specific_type_is_camel_case(self):
        payload = jsonld_to_ada(FULL_JSONLD)
        self.assertIn("specificType", payload)
