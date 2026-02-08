"""Tests for person/org pick lists, variable panel, distribution, MIME types, and schema defaults injection."""

import json
import unittest
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from records.models import KnownOrganization, KnownPerson, Profile, Record
from records.services import extract_known_entities, upsert_known_entities
from records.uischema_injection import (
    MIME_TYPE_ENUM,
    MIME_TYPE_OPTIONS,
    inject_schema_defaults,
    inject_uischema,
)

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
        {
            "type": "Group",
            "label": "Distribution",
            "elements": [
                {
                    "type": "Control",
                    "scope": "#/properties/schema:distribution",
                    "label": "Distributions",
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

# Schema that mimics the real variableMeasured structure
VARIABLE_MEASURED_SCHEMA = {
    "type": "object",
    "properties": {
        "schema:name": {"type": "string"},
        "schema:variableMeasured": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "@type": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "schema:name": {"type": "string"},
                },
                "required": ["@type", "schema:name"],
            },
        },
    },
}


# Schema that mimics the real distribution structure
DISTRIBUTION_SCHEMA = {
    "type": "object",
    "properties": {
        "schema:name": {"type": "string"},
        "schema:distribution": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "@type": {"type": "array", "items": {"type": "string"}},
                    "schema:name": {"type": "string"},
                    "schema:description": {"type": "string"},
                    "schema:contentUrl": {"type": "string", "format": "uri"},
                    "schema:encodingFormat": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "schema:hasPart": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "schema:name": {"type": "string"},
                                "schema:description": {"type": "string"},
                                "schema:encodingFormat": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
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


class VocabularyInjectionDisabledTest(TestCase):
    """With VOCABULARY_ENABLED=False (default), no vocabulary is injected."""

    def test_creator_no_vocabulary(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        creator = result["elements"][0]
        self.assertNotIn("vocabulary", creator.get("options", {}))

    def test_contributor_no_vocabulary(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        contrib = result["elements"][1]
        self.assertNotIn("vocabulary", contrib.get("options", {}))

    def test_provider_no_vocabulary(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        provider = result["elements"][3]
        self.assertNotIn("vocabulary", provider.get("options", {}))

    def test_publisher_name_no_vocabulary(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        pub_name = result["elements"][4]
        self.assertNotIn("vocabulary", pub_name.get("options", {}))


class VocabularyInjectionEnabledTest(TestCase):
    """With VOCABULARY_ENABLED=True, vocabulary is injected on person/org controls."""

    def _inject_with_vocab_enabled(self, uischema):
        with mock.patch("records.uischema_injection.VOCABULARY_ENABLED", True):
            return inject_uischema(uischema)

    def test_creator_gets_vocabulary(self):
        result = self._inject_with_vocab_enabled(SAMPLE_UISCHEMA)
        creator = result["elements"][0]
        self.assertIn("vocabulary", creator["options"])
        vocab = creator["options"]["vocabulary"]
        self.assertEqual(vocab["jsonUrl"], "/api/catalog/persons/")

    def test_contributor_gets_vocabulary(self):
        result = self._inject_with_vocab_enabled(SAMPLE_UISCHEMA)
        contrib = result["elements"][1]
        self.assertIn("vocabulary", contrib["options"])
        self.assertEqual(contrib["options"]["vocabulary"]["jsonUrl"], "/api/catalog/persons/")

    def test_maintainer_nested_in_group_gets_vocabulary(self):
        result = self._inject_with_vocab_enabled(SAMPLE_UISCHEMA)
        group = result["elements"][2]
        maintainer = group["elements"][0]
        self.assertIn("vocabulary", maintainer["options"])
        self.assertEqual(maintainer["options"]["vocabulary"]["jsonUrl"], "/api/catalog/persons/")

    def test_provider_gets_org_vocabulary(self):
        result = self._inject_with_vocab_enabled(SAMPLE_UISCHEMA)
        provider = result["elements"][3]
        self.assertIn("vocabulary", provider["options"])
        self.assertEqual(provider["options"]["vocabulary"]["jsonUrl"], "/api/catalog/organizations/")

    def test_publisher_name_gets_org_vocabulary(self):
        result = self._inject_with_vocab_enabled(SAMPLE_UISCHEMA)
        pub_name = result["elements"][4]
        self.assertIn("vocabulary", pub_name["options"])
        self.assertEqual(pub_name["options"]["vocabulary"]["jsonUrl"], "/api/catalog/organizations/")

    def test_person_vocabulary_value_mapping(self):
        result = self._inject_with_vocab_enabled(SAMPLE_UISCHEMA)
        vocab = result["elements"][0]["options"]["vocabulary"]
        self.assertIn("schema:name", vocab["value"])
        self.assertIn("schema:identifier", vocab["value"])
        self.assertIn("schema:affiliation", vocab["value"])
        self.assertTrue(vocab["value"]["schema:identifier"]["hidden"])


class VariablePanelInjectionTest(TestCase):
    def _get_variable_detail(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        var_group = result["elements"][5]
        var_ctrl = var_group["elements"][0]
        return var_ctrl["options"]["detail"]

    def test_variable_detail_replaced(self):
        detail = self._get_variable_detail()
        self.assertEqual(detail["type"], "VerticalLayout")
        # name, propertyID, description, _showAdvanced toggle, Advanced group
        self.assertEqual(len(detail["elements"]), 5)

    def test_variable_basic_fields(self):
        detail = self._get_variable_detail()
        labels = [el.get("label") for el in detail["elements"][:3]]
        self.assertEqual(labels, ["Name", "Property ID", "Description"])

    def test_variable_show_advanced_toggle(self):
        detail = self._get_variable_detail()
        toggle = detail["elements"][3]
        self.assertEqual(toggle["type"], "Control")
        self.assertEqual(toggle["scope"], "#/properties/_showAdvanced")
        self.assertEqual(toggle["label"], "Show Advanced Options")

    def test_variable_advanced_group_has_rule(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
        self.assertEqual(advanced["type"], "Group")
        self.assertEqual(advanced["label"], "Advanced")
        self.assertIn("rule", advanced)
        self.assertEqual(advanced["rule"]["effect"], "SHOW")

    def test_variable_advanced_rule_is_or_condition(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
        condition = advanced["rule"]["condition"]
        self.assertEqual(condition["type"], "OR")
        # _showAdvanced + 5 field conditions
        self.assertEqual(len(condition["conditions"]), 6)

    def test_variable_advanced_rule_toggle_condition(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
        toggle_cond = advanced["rule"]["condition"]["conditions"][0]
        self.assertEqual(toggle_cond["scope"], "#/properties/_showAdvanced")
        self.assertEqual(toggle_cond["schema"], {"const": True})

    def test_variable_advanced_rule_field_conditions_use_fail_when_undefined(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
        field_conditions = advanced["rule"]["condition"]["conditions"][1:]
        for cond in field_conditions:
            self.assertTrue(cond.get("failWhenUndefined"), f"Missing failWhenUndefined on {cond['scope']}")

    def test_variable_advanced_fields(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
        # measurementTechnique + 2 HorizontalLayouts
        self.assertEqual(len(advanced["elements"]), 3)
        self.assertEqual(advanced["elements"][0]["label"], "Measurement Technique")

    def test_variable_element_label_prop(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        var_ctrl = result["elements"][5]["elements"][0]
        self.assertEqual(var_ctrl["options"]["elementLabelProp"], "schema:name")

    def test_description_is_multiline(self):
        detail = self._get_variable_detail()
        desc = detail["elements"][2]
        self.assertTrue(desc["options"]["multi"])

    def test_advanced_horizontal_layouts(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
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

    def test_does_not_mutate_original(self):
        original_copy = json.loads(json.dumps(SAMPLE_UISCHEMA))
        inject_uischema(SAMPLE_UISCHEMA)
        self.assertEqual(SAMPLE_UISCHEMA, original_copy)


class DefinedTermDetailTest(TestCase):
    """Test that DefinedTerm controls hide @type via explicit detail layouts."""

    def _get_variable_detail(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        return result["elements"][5]["elements"][0]["options"]["detail"]

    def test_property_id_has_detail_layout(self):
        detail = self._get_variable_detail()
        prop_id = detail["elements"][1]  # Property ID control
        self.assertIn("detail", prop_id.get("options", {}))

    def test_property_id_detail_excludes_at_type(self):
        detail = self._get_variable_detail()
        prop_id_detail = detail["elements"][1]["options"]["detail"]
        scopes = [el["scope"] for el in prop_id_detail["elements"]]
        self.assertNotIn("#/properties/@type", scopes)

    def test_property_id_detail_includes_defined_term_fields(self):
        detail = self._get_variable_detail()
        prop_id_detail = detail["elements"][1]["options"]["detail"]
        scopes = [el["scope"] for el in prop_id_detail["elements"]]
        self.assertIn("#/properties/schema:name", scopes)
        self.assertIn("#/properties/schema:identifier", scopes)
        self.assertIn("#/properties/schema:inDefinedTermSet", scopes)
        self.assertIn("#/properties/schema:termCode", scopes)

    def test_measurement_technique_has_detail_layout(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
        mt = advanced["elements"][0]  # Measurement Technique control
        self.assertIn("detail", mt.get("options", {}))

    def test_measurement_technique_detail_shows_only_name(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
        mt_detail = advanced["elements"][0]["options"]["detail"]
        self.assertEqual(len(mt_detail["elements"]), 1)
        self.assertEqual(mt_detail["elements"][0]["scope"], "#/properties/schema:name")

    def test_measurement_technique_detail_excludes_at_type(self):
        detail = self._get_variable_detail()
        advanced = detail["elements"][4]
        mt_detail = advanced["elements"][0]["options"]["detail"]
        scopes = [el["scope"] for el in mt_detail["elements"]]
        self.assertNotIn("#/properties/@type", scopes)


# ===================================================================
# Schema defaults injection tests
# ===================================================================


class SchemaDefaultsInjectionTest(TestCase):
    def test_injects_variable_measured_at_type_default(self):
        result = inject_schema_defaults(VARIABLE_MEASURED_SCHEMA)
        at_type = result["properties"]["schema:variableMeasured"]["items"]["properties"]["@type"]
        self.assertEqual(at_type["default"], ["schema:PropertyValue"])

    def test_does_not_overwrite_existing_default(self):
        schema = json.loads(json.dumps(VARIABLE_MEASURED_SCHEMA))
        schema["properties"]["schema:variableMeasured"]["items"]["properties"]["@type"]["default"] = [
            "cdi:InstanceVariable",
            "schema:PropertyValue",
        ]
        result = inject_schema_defaults(schema)
        at_type = result["properties"]["schema:variableMeasured"]["items"]["properties"]["@type"]
        self.assertEqual(at_type["default"], ["cdi:InstanceVariable", "schema:PropertyValue"])

    def test_does_not_mutate_original(self):
        original_copy = json.loads(json.dumps(VARIABLE_MEASURED_SCHEMA))
        inject_schema_defaults(VARIABLE_MEASURED_SCHEMA)
        self.assertEqual(VARIABLE_MEASURED_SCHEMA, original_copy)

    def test_schema_without_variable_measured_unchanged(self):
        result = inject_schema_defaults(SIMPLE_SCHEMA)
        self.assertEqual(result, SIMPLE_SCHEMA)

    def test_skips_non_array_at_type(self):
        """Only injects default for array-typed @type (not string const)."""
        schema = {
            "type": "object",
            "properties": {
                "schema:variableMeasured": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "@type": {
                                "type": "string",
                                "const": "schema:PropertyValue",
                            },
                        },
                    },
                },
            },
        }
        result = inject_schema_defaults(schema)
        at_type = result["properties"]["schema:variableMeasured"]["items"]["properties"]["@type"]
        self.assertNotIn("default", at_type)

    def test_injects_show_advanced_boolean(self):
        result = inject_schema_defaults(VARIABLE_MEASURED_SCHEMA)
        props = result["properties"]["schema:variableMeasured"]["items"]["properties"]
        self.assertIn("_showAdvanced", props)
        self.assertEqual(props["_showAdvanced"]["type"], "boolean")
        self.assertFalse(props["_showAdvanced"]["default"])

    def test_injects_distribution_type_selector(self):
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA)
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        self.assertIn("_distributionType", dist_props)
        self.assertEqual(dist_props["_distributionType"]["enum"], ["Data Download", "Web API"])
        self.assertEqual(dist_props["_distributionType"]["default"], "Data Download")

    def test_injects_webapi_properties(self):
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA)
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        self.assertIn("schema:serviceType", dist_props)
        self.assertIn("schema:documentation", dist_props)
        self.assertEqual(dist_props["schema:documentation"]["format"], "uri")

    def test_injects_mime_type_enum_on_encoding_format(self):
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA)
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        enc_items = dist_props["schema:encodingFormat"]["items"]
        self.assertIn("enum", enc_items)
        self.assertEqual(enc_items["enum"], MIME_TYPE_ENUM)

    def test_injects_mime_type_enum_on_has_part_encoding_format(self):
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA)
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        hp_enc_items = dist_props["schema:hasPart"]["items"]["properties"]["schema:encodingFormat"]["items"]
        self.assertIn("enum", hp_enc_items)
        self.assertEqual(hp_enc_items["enum"], MIME_TYPE_ENUM)

    def test_schema_without_distribution_unchanged(self):
        """Distribution injection skips schemas without schema:distribution."""
        result = inject_schema_defaults(SIMPLE_SCHEMA)
        self.assertNotIn("schema:distribution", result.get("properties", {}))


# ===================================================================
# ProfileSerializer injection test
# ===================================================================


class ProfileSerializerInjectionTest(TestCase):
    def test_profile_detail_injects_variable_layout(self):
        profile = Profile.objects.create(
            name="testProfile",
            schema=SIMPLE_SCHEMA,
            uischema=SAMPLE_UISCHEMA,
        )
        self.client = APIClient()
        resp = self.client.get(f"/api/catalog/profiles/{profile.name}/")
        self.assertEqual(resp.status_code, 200)
        uischema = resp.json()["uischema"]
        # Variable detail should be injected
        var_ctrl = uischema["elements"][5]["elements"][0]
        detail = var_ctrl["options"]["detail"]
        # name, propertyID, description, _showAdvanced toggle, Advanced group
        self.assertEqual(len(detail["elements"]), 5)

    def test_profile_detail_does_not_inject_vocabulary(self):
        """With VOCABULARY_ENABLED=False, no vocabulary on creator."""
        profile = Profile.objects.create(
            name="testProfile2",
            schema=SIMPLE_SCHEMA,
            uischema=SAMPLE_UISCHEMA,
        )
        self.client = APIClient()
        resp = self.client.get(f"/api/catalog/profiles/{profile.name}/")
        self.assertEqual(resp.status_code, 200)
        uischema = resp.json()["uischema"]
        creator = uischema["elements"][0]
        self.assertNotIn("vocabulary", creator.get("options", {}))

    def test_profile_detail_injects_schema_defaults(self):
        profile = Profile.objects.create(
            name="testProfile3",
            schema=VARIABLE_MEASURED_SCHEMA,
            uischema=SAMPLE_UISCHEMA,
        )
        self.client = APIClient()
        resp = self.client.get(f"/api/catalog/profiles/{profile.name}/")
        self.assertEqual(resp.status_code, 200)
        schema = resp.json()["schema"]
        at_type = schema["properties"]["schema:variableMeasured"]["items"]["properties"]["@type"]
        self.assertEqual(at_type["default"], ["schema:PropertyValue"])


# ===================================================================
# Record create/update triggers upsert
# ===================================================================


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


# ===================================================================
# Distribution UISchema injection tests
# ===================================================================


class DistributionInjectionTest(TestCase):
    def _get_distribution_detail(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        dist_group = result["elements"][6]
        dist_ctrl = dist_group["elements"][0]
        return dist_ctrl["options"]["detail"]

    def test_distribution_detail_injected(self):
        detail = self._get_distribution_detail()
        self.assertEqual(detail["type"], "VerticalLayout")
        # _distributionType, name, description, contentUrl, encodingFormat, hasPart, serviceType, documentation
        self.assertEqual(len(detail["elements"]), 8)

    def test_distribution_type_selector(self):
        detail = self._get_distribution_detail()
        type_ctrl = detail["elements"][0]
        self.assertEqual(type_ctrl["scope"], "#/properties/_distributionType")
        self.assertEqual(type_ctrl["label"], "Distribution Type")

    def test_content_url_has_show_rule(self):
        detail = self._get_distribution_detail()
        content_url = detail["elements"][3]
        self.assertEqual(content_url["scope"], "#/properties/schema:contentUrl")
        self.assertEqual(content_url["rule"]["effect"], "SHOW")
        self.assertEqual(
            content_url["rule"]["condition"]["schema"], {"const": "Data Download"}
        )

    def test_encoding_format_has_show_rule(self):
        detail = self._get_distribution_detail()
        enc_fmt = detail["elements"][4]
        self.assertEqual(enc_fmt["scope"], "#/properties/schema:encodingFormat")
        self.assertEqual(enc_fmt["rule"]["effect"], "SHOW")
        self.assertEqual(
            enc_fmt["rule"]["condition"]["schema"], {"const": "Data Download"}
        )

    def test_archive_contents_has_and_rule(self):
        detail = self._get_distribution_detail()
        has_part = detail["elements"][5]
        self.assertEqual(has_part["scope"], "#/properties/schema:hasPart")
        self.assertEqual(has_part["label"], "Archive Contents")
        rule = has_part["rule"]
        self.assertEqual(rule["effect"], "SHOW")
        self.assertEqual(rule["condition"]["type"], "AND")
        conditions = rule["condition"]["conditions"]
        self.assertEqual(len(conditions), 2)
        # First condition: _distributionType == "Data Download"
        self.assertEqual(conditions[0]["schema"], {"const": "Data Download"})
        # Second condition: encodingFormat contains "application/zip"
        self.assertEqual(
            conditions[1]["schema"], {"contains": {"const": "application/zip"}}
        )

    def test_service_type_has_webapi_rule(self):
        detail = self._get_distribution_detail()
        svc = detail["elements"][6]
        self.assertEqual(svc["scope"], "#/properties/schema:serviceType")
        self.assertEqual(svc["rule"]["effect"], "SHOW")
        self.assertEqual(svc["rule"]["condition"]["schema"], {"const": "Web API"})

    def test_documentation_has_webapi_rule(self):
        detail = self._get_distribution_detail()
        doc = detail["elements"][7]
        self.assertEqual(doc["scope"], "#/properties/schema:documentation")
        self.assertEqual(doc["rule"]["effect"], "SHOW")
        self.assertEqual(doc["rule"]["condition"]["schema"], {"const": "Web API"})

    def test_has_part_detail_layout(self):
        detail = self._get_distribution_detail()
        has_part = detail["elements"][5]
        hp_detail = has_part["options"]["detail"]
        self.assertEqual(hp_detail["type"], "VerticalLayout")
        scopes = [el["scope"] for el in hp_detail["elements"]]
        self.assertIn("#/properties/schema:name", scopes)
        self.assertIn("#/properties/schema:encodingFormat", scopes)

    def test_distribution_element_label_prop(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        dist_ctrl = result["elements"][6]["elements"][0]
        self.assertEqual(dist_ctrl["options"]["elementLabelProp"], "schema:name")


# ===================================================================
# MIME type options tests
# ===================================================================


class MimeTypeOptionsTest(TestCase):
    def test_mime_type_options_count(self):
        self.assertEqual(len(MIME_TYPE_OPTIONS), 26)

    def test_each_option_has_const_and_title(self):
        for opt in MIME_TYPE_OPTIONS:
            self.assertIn("const", opt)
            self.assertIn("title", opt)

    def test_application_zip_present(self):
        consts = [o["const"] for o in MIME_TYPE_OPTIONS]
        self.assertIn("application/zip", consts)

    def test_text_csv_present(self):
        consts = [o["const"] for o in MIME_TYPE_OPTIONS]
        self.assertIn("text/csv", consts)

    def test_title_format_includes_extension_and_media_type(self):
        csv_opt = next(o for o in MIME_TYPE_OPTIONS if o["const"] == "text/csv")
        self.assertIn(".csv", csv_opt["title"])
        self.assertIn("text/csv", csv_opt["title"])

    def test_options_sorted_by_const(self):
        consts = [o["const"] for o in MIME_TYPE_OPTIONS]
        self.assertEqual(consts, sorted(consts))


# ===================================================================
# Serializer data cleanup tests
# ===================================================================


class SerializerDataCleanupTest(TestCase):
    """Test that validate() strips UI-only fields and sets @type correctly."""

    def setUp(self):
        self.profile = Profile.objects.create(
            name="cleanupTest",
            schema={},  # No validation
        )

    def _make_attrs(self, jsonld):
        return {"jsonld": jsonld, "profile": self.profile}

    def test_strips_show_advanced_from_variables(self):
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:variableMeasured": [
                {"schema:name": "Temp", "_showAdvanced": True},
                {"schema:name": "Depth", "_showAdvanced": False},
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        for var in attrs["jsonld"]["schema:variableMeasured"]:
            self.assertNotIn("_showAdvanced", var)

    def test_strips_distribution_type_and_sets_data_download(self):
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {"schema:name": "File", "_distributionType": "Data Download"},
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertNotIn("_distributionType", dist)
        self.assertEqual(dist["@type"], ["schema:DataDownload"])

    def test_strips_distribution_type_and_sets_web_api(self):
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {"schema:name": "API", "_distributionType": "Web API"},
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertNotIn("_distributionType", dist)
        self.assertEqual(dist["@type"], ["schema:WebAPI"])

    def test_no_distribution_type_defaults_to_data_download(self):
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {"schema:name": "File"},
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertEqual(dist["@type"], ["schema:DataDownload"])

    def test_existing_at_type_preserved_when_no_distribution_type(self):
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {"schema:name": "File", "@type": ["schema:DataDownload"]},
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertEqual(dist["@type"], ["schema:DataDownload"])

    def test_web_api_overwrites_existing_at_type(self):
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {
                    "schema:name": "API",
                    "@type": ["schema:DataDownload"],
                    "_distributionType": "Web API",
                },
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertEqual(dist["@type"], ["schema:WebAPI"])
