"""Tests for person/org pick lists and variable panel UISchema injection."""

import json

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from records.models import KnownOrganization, KnownPerson, Profile, Record
from records.services import extract_known_entities, upsert_known_entities
from records.uischema_injection import inject_vocabulary

User = get_user_model()

# ---------------------------------------------------------------------------
# Sample JSON-LD fixtures
# ---------------------------------------------------------------------------

SAMPLE_JSONLD = {
    "@context": {"schema": "http://schema.org/"},
    "@type": ["schema:Dataset"],
    "@id": "https://doi.org/10.1234/test",
    "schema:name": "Test Dataset",
    "schema:creator": {
        "@list": [
            {
                "@type": "schema:Person",
                "schema:name": "Joe Test",
                "schema:identifier": {
                    "@type": "schema:PropertyValue",
                    "schema:propertyID": "ORCID",
                    "schema:value": "0000-0002-1234-5678",
                    "schema:url": "https://orcid.org/0000-0002-1234-5678",
                },
                "schema:affiliation": {
                    "@type": "schema:Organization",
                    "schema:name": "University of Arizona",
                    "schema:identifier": {
                        "@type": "schema:PropertyValue",
                        "schema:propertyID": "ROR",
                        "schema:value": "03m2x1q45",
                        "schema:url": "https://ror.org/03m2x1q45",
                    },
                },
            },
            {
                "@type": "schema:Person",
                "schema:name": "Jane Doe",
            },
        ]
    },
    "schema:contributor": [
        {
            "@type": "schema:Person",
            "schema:name": "Bob Contrib",
            "schema:identifier": {
                "@type": "schema:PropertyValue",
                "schema:propertyID": "ORCID",
                "schema:value": "0000-0003-9999-0000",
                "schema:url": "https://orcid.org/0000-0003-9999-0000",
            },
        }
    ],
    "schema:subjectOf": {
        "schema:maintainer": {
            "@type": "schema:Person",
            "schema:name": "Maint Person",
        }
    },
    "schema:publisher": {
        "@type": "schema:Organization",
        "schema:name": "IEDA",
        "schema:identifier": {
            "@type": "schema:PropertyValue",
            "schema:propertyID": "ROR",
            "schema:value": "02fjz5e27",
            "schema:url": "https://ror.org/02fjz5e27",
        },
    },
    "schema:provider": [
        {
            "@type": "schema:Organization",
            "schema:name": "EarthChem",
        }
    ],
}

SAMPLE_UISCHEMA = {
    "type": "VerticalLayout",
    "elements": [
        {
            "type": "Control",
            "scope": "#/properties/schema:creator/properties/@list",
            "label": "Creators",
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:contributor",
            "label": "Contributors",
        },
        {
            "type": "Group",
            "label": "Metadata",
            "elements": [
                {
                    "type": "Control",
                    "scope": "#/properties/schema:subjectOf/properties/schema:maintainer",
                    "label": "Maintainer",
                }
            ],
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:provider",
            "label": "Provider",
        },
        {
            "type": "Control",
            "scope": "#/properties/schema:publisher/properties/schema:name",
            "label": "Publisher Name",
        },
        {
            "type": "Group",
            "label": "Variables",
            "elements": [
                {
                    "type": "Control",
                    "scope": "#/properties/schema:variableMeasured",
                    "label": "Variables",
                    "options": {
                        "elementLabelProp": "schema:name",
                        "detail": {
                            "type": "VerticalLayout",
                            "elements": [
                                {
                                    "type": "Control",
                                    "scope": "#/properties/schema:name",
                                }
                            ],
                        },
                    },
                }
            ],
        },
    ],
}

SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "schema:name": {"type": "string"},
    },
}


# ===================================================================
# Entity extraction tests
# ===================================================================


class ExtractKnownEntitiesTest(TestCase):
    def test_extracts_creators(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        names = [p["name"] for p in entities["persons"]]
        self.assertIn("Joe Test", names)
        self.assertIn("Jane Doe", names)

    def test_extracts_creator_identifier(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        joe = next(p for p in entities["persons"] if p["name"] == "Joe Test")
        self.assertEqual(joe["identifier_type"], "ORCID")
        self.assertEqual(joe["identifier_value"], "0000-0002-1234-5678")
        self.assertEqual(joe["identifier_url"], "https://orcid.org/0000-0002-1234-5678")

    def test_extracts_creator_affiliation(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        joe = next(p for p in entities["persons"] if p["name"] == "Joe Test")
        self.assertEqual(joe["affiliation_name"], "University of Arizona")
        self.assertEqual(joe["affiliation_identifier_type"], "ROR")
        self.assertEqual(joe["affiliation_identifier_value"], "03m2x1q45")

    def test_person_without_identifier_has_empty_strings(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        jane = next(p for p in entities["persons"] if p["name"] == "Jane Doe")
        self.assertEqual(jane["identifier_value"], "")
        self.assertEqual(jane["affiliation_name"], "")

    def test_extracts_contributors(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        names = [p["name"] for p in entities["persons"]]
        self.assertIn("Bob Contrib", names)

    def test_extracts_maintainer(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        names = [p["name"] for p in entities["persons"]]
        self.assertIn("Maint Person", names)

    def test_extracts_publisher_org(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        org_names = [o["name"] for o in entities["organizations"]]
        self.assertIn("IEDA", org_names)

    def test_extracts_provider_org(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        org_names = [o["name"] for o in entities["organizations"]]
        self.assertIn("EarthChem", org_names)

    def test_extracts_affiliation_as_org(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        org_names = [o["name"] for o in entities["organizations"]]
        self.assertIn("University of Arizona", org_names)

    def test_publisher_identifier(self):
        entities = extract_known_entities(SAMPLE_JSONLD)
        ieda = next(o for o in entities["organizations"] if o["name"] == "IEDA")
        self.assertEqual(ieda["identifier_type"], "ROR")
        self.assertEqual(ieda["identifier_value"], "02fjz5e27")

    def test_empty_jsonld(self):
        entities = extract_known_entities({})
        self.assertEqual(entities["persons"], [])
        self.assertEqual(entities["organizations"], [])

    def test_creator_as_flat_list(self):
        """schema:creator can be a flat list (no @list wrapper)."""
        jsonld = {
            "schema:creator": [
                {"@type": "schema:Person", "schema:name": "Flat Creator"}
            ]
        }
        entities = extract_known_entities(jsonld)
        self.assertEqual(entities["persons"][0]["name"], "Flat Creator")

    def test_single_contributor_dict(self):
        """schema:contributor can be a single dict instead of an array."""
        jsonld = {
            "schema:contributor": {
                "@type": "schema:Person",
                "schema:name": "Solo Contrib",
            }
        }
        entities = extract_known_entities(jsonld)
        self.assertEqual(entities["persons"][0]["name"], "Solo Contrib")

    def test_maintainer_as_list(self):
        """schema:maintainer can be a list."""
        jsonld = {
            "schema:subjectOf": {
                "schema:maintainer": [
                    {"@type": "schema:Person", "schema:name": "M1"},
                    {"@type": "schema:Person", "schema:name": "M2"},
                ]
            }
        }
        entities = extract_known_entities(jsonld)
        names = [p["name"] for p in entities["persons"]]
        self.assertIn("M1", names)
        self.assertIn("M2", names)

    def test_provider_single_dict(self):
        """schema:provider can be a single dict."""
        jsonld = {
            "schema:provider": {
                "@type": "schema:Organization",
                "schema:name": "Solo Provider",
            }
        }
        entities = extract_known_entities(jsonld)
        self.assertEqual(entities["organizations"][0]["name"], "Solo Provider")


# ===================================================================
# Upsert tests
# ===================================================================


class UpsertKnownEntitiesTest(TestCase):
    def test_creates_person_records(self):
        upsert_known_entities(SAMPLE_JSONLD)
        self.assertTrue(KnownPerson.objects.filter(name="Joe Test").exists())
        self.assertTrue(KnownPerson.objects.filter(name="Jane Doe").exists())
        self.assertTrue(KnownPerson.objects.filter(name="Bob Contrib").exists())
        self.assertTrue(KnownPerson.objects.filter(name="Maint Person").exists())

    def test_creates_org_records(self):
        upsert_known_entities(SAMPLE_JSONLD)
        self.assertTrue(KnownOrganization.objects.filter(name="IEDA").exists())
        self.assertTrue(KnownOrganization.objects.filter(name="EarthChem").exists())
        self.assertTrue(KnownOrganization.objects.filter(name="University of Arizona").exists())

    def test_upsert_updates_existing(self):
        """Second upsert should update, not duplicate."""
        upsert_known_entities(SAMPLE_JSONLD)
        count_before = KnownPerson.objects.count()
        upsert_known_entities(SAMPLE_JSONLD)
        count_after = KnownPerson.objects.count()
        self.assertEqual(count_before, count_after)

    def test_same_name_different_id_creates_separate(self):
        """Same name with different ORCID creates separate entries."""
        jsonld1 = {
            "schema:creator": {
                "@list": [
                    {
                        "schema:name": "John Smith",
                        "schema:identifier": {
                            "schema:propertyID": "ORCID",
                            "schema:value": "0000-0000-0000-0001",
                            "schema:url": "https://orcid.org/0000-0000-0000-0001",
                        },
                    }
                ]
            }
        }
        jsonld2 = {
            "schema:creator": {
                "@list": [
                    {
                        "schema:name": "John Smith",
                        "schema:identifier": {
                            "schema:propertyID": "ORCID",
                            "schema:value": "0000-0000-0000-0002",
                            "schema:url": "https://orcid.org/0000-0000-0000-0002",
                        },
                    }
                ]
            }
        }
        upsert_known_entities(jsonld1)
        upsert_known_entities(jsonld2)
        self.assertEqual(KnownPerson.objects.filter(name="John Smith").count(), 2)

    def test_person_identifier_stored_correctly(self):
        upsert_known_entities(SAMPLE_JSONLD)
        joe = KnownPerson.objects.get(name="Joe Test")
        self.assertEqual(joe.identifier_type, "ORCID")
        self.assertEqual(joe.identifier_value, "0000-0002-1234-5678")
        self.assertEqual(joe.identifier_url, "https://orcid.org/0000-0002-1234-5678")

    def test_person_affiliation_stored_correctly(self):
        upsert_known_entities(SAMPLE_JSONLD)
        joe = KnownPerson.objects.get(name="Joe Test")
        self.assertEqual(joe.affiliation_name, "University of Arizona")
        self.assertEqual(joe.affiliation_identifier_type, "ROR")
        self.assertEqual(joe.affiliation_identifier_value, "03m2x1q45")

    def test_org_identifier_stored_correctly(self):
        upsert_known_entities(SAMPLE_JSONLD)
        ieda = KnownOrganization.objects.get(name="IEDA")
        self.assertEqual(ieda.identifier_type, "ROR")
        self.assertEqual(ieda.identifier_value, "02fjz5e27")


# ===================================================================
# Search API endpoint tests
# ===================================================================


class PersonsSearchAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        upsert_known_entities(SAMPLE_JSONLD)

    def test_search_by_name(self):
        resp = self.client.get("/api/catalog/persons/", {"q": "Joe"})
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["schema:name"], "Joe Test")

    def test_search_returns_identifier(self):
        resp = self.client.get("/api/catalog/persons/", {"q": "Joe"})
        results = resp.json()["results"]
        ident = results[0]["schema:identifier"]
        self.assertEqual(ident["schema:propertyID"], "ORCID")
        self.assertEqual(ident["schema:value"], "0000-0002-1234-5678")

    def test_search_returns_affiliation(self):
        resp = self.client.get("/api/catalog/persons/", {"q": "Joe"})
        results = resp.json()["results"]
        affil = results[0]["schema:affiliation"]
        self.assertEqual(affil["schema:name"], "University of Arizona")

    def test_search_without_identifier_omits_field(self):
        resp = self.client.get("/api/catalog/persons/", {"q": "Jane"})
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertNotIn("schema:identifier", results[0])
        self.assertNotIn("schema:affiliation", results[0])

    def test_empty_search_returns_all(self):
        resp = self.client.get("/api/catalog/persons/")
        results = resp.json()["results"]
        self.assertEqual(len(results), 4)  # Joe, Jane, Bob, Maint

    def test_case_insensitive_search(self):
        resp = self.client.get("/api/catalog/persons/", {"q": "joe"})
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)

    def test_no_match_returns_empty(self):
        resp = self.client.get("/api/catalog/persons/", {"q": "zzzznotfound"})
        results = resp.json()["results"]
        self.assertEqual(len(results), 0)

    def test_no_auth_required(self):
        """Persons search is public."""
        self.client.logout()
        resp = self.client.get("/api/catalog/persons/", {"q": "Joe"})
        self.assertEqual(resp.status_code, 200)


class OrganizationsSearchAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        upsert_known_entities(SAMPLE_JSONLD)

    def test_search_by_name(self):
        resp = self.client.get("/api/catalog/organizations/", {"q": "IEDA"})
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["schema:name"], "IEDA")

    def test_search_returns_identifier(self):
        resp = self.client.get("/api/catalog/organizations/", {"q": "IEDA"})
        results = resp.json()["results"]
        ident = results[0]["schema:identifier"]
        self.assertEqual(ident["schema:propertyID"], "ROR")
        self.assertEqual(ident["schema:value"], "02fjz5e27")

    def test_org_without_identifier_omits_field(self):
        resp = self.client.get("/api/catalog/organizations/", {"q": "EarthChem"})
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertNotIn("schema:identifier", results[0])

    def test_empty_search_returns_all(self):
        resp = self.client.get("/api/catalog/organizations/")
        results = resp.json()["results"]
        self.assertEqual(len(results), 3)  # IEDA, EarthChem, University of Arizona


# ===================================================================
# UISchema injection tests
# ===================================================================


class VocabularyInjectionTest(TestCase):
    def test_creator_gets_vocabulary(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        creator = result["elements"][0]
        self.assertIn("vocabulary", creator["options"])
        vocab = creator["options"]["vocabulary"]
        self.assertEqual(vocab["jsonUrl"], "/api/catalog/persons/")

    def test_contributor_gets_vocabulary(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        contrib = result["elements"][1]
        self.assertIn("vocabulary", contrib["options"])
        self.assertEqual(contrib["options"]["vocabulary"]["jsonUrl"], "/api/catalog/persons/")

    def test_maintainer_nested_in_group_gets_vocabulary(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        group = result["elements"][2]
        maintainer = group["elements"][0]
        self.assertIn("vocabulary", maintainer["options"])
        self.assertEqual(maintainer["options"]["vocabulary"]["jsonUrl"], "/api/catalog/persons/")

    def test_provider_gets_org_vocabulary(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        provider = result["elements"][3]
        self.assertIn("vocabulary", provider["options"])
        self.assertEqual(provider["options"]["vocabulary"]["jsonUrl"], "/api/catalog/organizations/")

    def test_publisher_name_gets_org_vocabulary(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        pub_name = result["elements"][4]
        self.assertIn("vocabulary", pub_name["options"])
        self.assertEqual(pub_name["options"]["vocabulary"]["jsonUrl"], "/api/catalog/organizations/")

    def test_does_not_mutate_original(self):
        original_copy = json.loads(json.dumps(SAMPLE_UISCHEMA))
        inject_vocabulary(SAMPLE_UISCHEMA)
        self.assertEqual(SAMPLE_UISCHEMA, original_copy)

    def test_person_vocabulary_value_mapping(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        vocab = result["elements"][0]["options"]["vocabulary"]
        self.assertIn("schema:name", vocab["value"])
        self.assertIn("schema:identifier", vocab["value"])
        self.assertIn("schema:affiliation", vocab["value"])
        self.assertTrue(vocab["value"]["schema:identifier"]["hidden"])


class VariablePanelInjectionTest(TestCase):
    def test_variable_detail_replaced(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        var_group = result["elements"][5]
        var_ctrl = var_group["elements"][0]
        detail = var_ctrl["options"]["detail"]
        self.assertEqual(detail["type"], "VerticalLayout")
        self.assertEqual(len(detail["elements"]), 4)

    def test_variable_basic_fields(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        detail = result["elements"][5]["elements"][0]["options"]["detail"]
        labels = [el.get("label") for el in detail["elements"][:3]]
        self.assertEqual(labels, ["Name", "Property ID", "Description"])

    def test_variable_advanced_group(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        detail = result["elements"][5]["elements"][0]["options"]["detail"]
        advanced = detail["elements"][3]
        self.assertEqual(advanced["type"], "Group")
        self.assertEqual(advanced["label"], "Advanced")
        self.assertTrue(advanced["options"]["collapsed"])
        self.assertTrue(advanced["options"]["expandWhenPopulated"])

    def test_variable_advanced_fields(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        detail = result["elements"][5]["elements"][0]["options"]["detail"]
        advanced = detail["elements"][3]
        # measurementTechnique + 2 HorizontalLayouts
        self.assertEqual(len(advanced["elements"]), 3)
        self.assertEqual(advanced["elements"][0]["label"], "Measurement Technique")

    def test_variable_element_label_prop(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        var_ctrl = result["elements"][5]["elements"][0]
        self.assertEqual(var_ctrl["options"]["elementLabelProp"], "schema:name")

    def test_description_is_multiline(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        detail = result["elements"][5]["elements"][0]["options"]["detail"]
        desc = detail["elements"][2]
        self.assertTrue(desc["options"]["multi"])

    def test_advanced_horizontal_layouts(self):
        result = inject_vocabulary(SAMPLE_UISCHEMA)
        detail = result["elements"][5]["elements"][0]["options"]["detail"]
        advanced = detail["elements"][3]
        # unitText + unitCode horizontal
        h1 = advanced["elements"][1]
        self.assertEqual(h1["type"], "HorizontalLayout")
        self.assertEqual(h1["elements"][0]["label"], "Unit Text")
        self.assertEqual(h1["elements"][1]["label"], "Unit Code")
        # minValue + maxValue horizontal
        h2 = advanced["elements"][2]
        self.assertEqual(h2["type"], "HorizontalLayout")
        self.assertEqual(h2["elements"][0]["label"], "Min Value")
        self.assertEqual(h2["elements"][1]["label"], "Max Value")


# ===================================================================
# ProfileSerializer injection test
# ===================================================================


class ProfileSerializerInjectionTest(TestCase):
    def test_profile_detail_injects_vocabulary(self):
        profile = Profile.objects.create(
            name="testProfile",
            schema=SIMPLE_SCHEMA,
            uischema=SAMPLE_UISCHEMA,
        )
        self.client = APIClient()
        resp = self.client.get(f"/api/catalog/profiles/{profile.name}/")
        self.assertEqual(resp.status_code, 200)
        uischema = resp.json()["uischema"]
        # Creator should have vocabulary injected
        creator = uischema["elements"][0]
        self.assertIn("vocabulary", creator.get("options", {}))


# ===================================================================
# Record create/update triggers upsert
# ===================================================================


import unittest


def requires_postgresql(test_func):
    """Skip test if not running on PostgreSQL (ArrayField/GinIndex are PG-only)."""
    def wrapper(*args, **kwargs):
        if connection.vendor != "postgresql":
            raise unittest.SkipTest("Requires PostgreSQL (ArrayField/GinIndex)")
        return test_func(*args, **kwargs)
    wrapper.__name__ = test_func.__name__
    wrapper.__doc__ = test_func.__doc__
    return wrapper


class RecordUpsertIntegrationTest(TestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL (ArrayField/GinIndex)")
        self.user = User.objects.create_user(
            username="testuser", password="testpass", orcid="0000-0000-0000-0099"
        )
        self.profile = Profile.objects.create(
            name="testProfile",
            schema={},  # No validation
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_record_upserts_entities(self):
        resp = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": SAMPLE_JSONLD},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(KnownPerson.objects.filter(name="Joe Test").exists())
        self.assertTrue(KnownOrganization.objects.filter(name="IEDA").exists())

    def test_update_record_upserts_entities(self):
        # Create a minimal record first
        resp = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": {"schema:name": "Bare"}},
            format="json",
        )
        record_id = resp.json()["id"]
        self.assertEqual(KnownPerson.objects.count(), 0)

        # Update with full JSON-LD
        resp = self.client.patch(
            f"/api/catalog/records/{record_id}/",
            {"jsonld": SAMPLE_JSONLD},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(KnownPerson.objects.filter(name="Joe Test").exists())
