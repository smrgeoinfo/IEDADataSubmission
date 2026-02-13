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
    DATACUBE_COMPONENT_TYPES,
    DATACUBE_MIMES,
    DOCUMENT_COMPONENT_TYPES,
    DOCUMENT_MIMES,
    GENERIC_COMPONENT_TYPES,
    IMAGE_COMPONENT_TYPES,
    IMAGE_MIMES,
    MIME_TYPE_ENUM,
    MIME_TYPE_OPTIONS,
    PROFILE_COMPONENT_TYPES,
    STRUCTURED_DATA_MIMES,
    TABULAR_COMPONENT_TYPES,
    TABULAR_MIMES,
    _get_profile_category_components,
    _get_profile_mime_enum,
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


class MaintainerSuggestionTest(TestCase):
    """Test that person name suggestions are injected into the maintainer's name control."""

    UISCHEMA_WITH_MAINTAINER_DETAIL = {
        "type": "VerticalLayout",
        "elements": [
            {
                "type": "Control",
                "scope": "#/properties/schema:subjectOf/properties/schema:maintainer",
                "label": "Maintainer",
                "options": {
                    "detail": {
                        "type": "HorizontalLayout",
                        "elements": [
                            {"type": "Control", "scope": "#/properties/@type", "label": "Type"},
                            {"type": "Control", "scope": "#/properties/schema:name", "label": "Name"},
                        ],
                    }
                },
            }
        ],
    }

    def test_suggestion_injected_on_name_control(self):
        names = ["Alice Smith", "Bob Jones"]
        result = inject_uischema(self.UISCHEMA_WITH_MAINTAINER_DETAIL, person_names=names)
        maintainer = result["elements"][0]
        name_ctrl = maintainer["options"]["detail"]["elements"][1]
        self.assertEqual(name_ctrl["scope"], "#/properties/schema:name")
        self.assertEqual(name_ctrl["options"]["suggestion"], names)

    def test_no_suggestion_when_no_names(self):
        result = inject_uischema(self.UISCHEMA_WITH_MAINTAINER_DETAIL, person_names=None)
        maintainer = result["elements"][0]
        name_ctrl = maintainer["options"]["detail"]["elements"][1]
        self.assertNotIn("options", name_ctrl)

    def test_no_suggestion_when_empty_names(self):
        result = inject_uischema(self.UISCHEMA_WITH_MAINTAINER_DETAIL, person_names=[])
        maintainer = result["elements"][0]
        name_ctrl = maintainer["options"]["detail"]["elements"][1]
        self.assertNotIn("options", name_ctrl)

    def test_no_crash_without_detail(self):
        """Maintainer control without detail layout should not crash."""
        result = inject_uischema(SAMPLE_UISCHEMA, person_names=["Alice"])
        group = result["elements"][2]
        maintainer = group["elements"][0]
        # No detail, so no suggestion injected — just verify no error
        self.assertEqual(maintainer["scope"], "#/properties/schema:subjectOf/properties/schema:maintainer")


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
        self.assertEqual(at_type["default"], ["schema:PropertyValue", "cdi:InstanceVariable"])

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

    def test_injects_encoding_format_as_string_with_enum(self):
        """encodingFormat is replaced with a single string + MIME enum at serve time."""
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA)
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        enc_fmt = dist_props["schema:encodingFormat"]
        self.assertEqual(enc_fmt["type"], "string")
        self.assertEqual(enc_fmt["enum"], MIME_TYPE_ENUM)

    def test_injects_has_part_encoding_format_as_string_with_enum(self):
        """hasPart encodingFormat is replaced with single string + MIME enum."""
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA)
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        hp_enc = dist_props["schema:hasPart"]["items"]["properties"]["schema:encodingFormat"]
        self.assertEqual(hp_enc["type"], "string")
        self.assertEqual(hp_enc["enum"], MIME_TYPE_ENUM)

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
        self.assertEqual(at_type["default"], ["schema:PropertyValue", "cdi:InstanceVariable"])


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
        result = inject_uischema(SAMPLE_UISCHEMA, profile_name="adaProduct")
        dist_group = result["elements"][6]
        dist_ctrl = dist_group["elements"][0]
        return dist_ctrl["options"]["detail"]

    def test_distribution_detail_injected(self):
        detail = self._get_distribution_detail()
        self.assertEqual(detail["type"], "VerticalLayout")
        # _distributionType, name, description, contentUrl, encodingFormat, hasPart,
        # 4 file-type groups (image, tabular, datacube, document),
        # serviceType, documentation
        self.assertEqual(len(detail["elements"]), 12)

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
        # Second condition: encodingFormat == "application/zip" (string const)
        self.assertEqual(
            conditions[1]["schema"], {"const": "application/zip"}
        )

    def test_service_type_has_webapi_rule(self):
        detail = self._get_distribution_detail()
        svc = detail["elements"][10]
        self.assertEqual(svc["scope"], "#/properties/schema:serviceType")
        self.assertEqual(svc["rule"]["effect"], "SHOW")
        self.assertEqual(svc["rule"]["condition"]["schema"], {"const": "Web API"})

    def test_documentation_has_webapi_rule(self):
        detail = self._get_distribution_detail()
        doc = detail["elements"][11]
        self.assertEqual(doc["scope"], "#/properties/schema:documentation")
        self.assertEqual(doc["rule"]["effect"], "SHOW")
        self.assertEqual(doc["rule"]["condition"]["schema"], {"const": "Web API"})

    def test_has_part_detail_layout(self):
        detail = self._get_distribution_detail()
        has_part = detail["elements"][5]
        hp_detail = has_part["options"]["detail"]
        self.assertEqual(hp_detail["type"], "VerticalLayout")
        # name, HorizontalLayout(MIME+size), description, 4 MIME groups,
        # _showPhysicalStructure toggle, 2 physical structure groups
        self.assertEqual(len(hp_detail["elements"]), 10)
        self.assertEqual(
            hp_detail["elements"][0]["scope"], "#/properties/schema:name"
        )
        # encodingFormat is inside the HorizontalLayout at index 1
        horiz = hp_detail["elements"][1]
        self.assertEqual(horiz["type"], "HorizontalLayout")
        horiz_scopes = [el.get("scope") for el in horiz["elements"]]
        self.assertIn("#/properties/schema:encodingFormat", horiz_scopes)

    def test_has_part_nested_archive(self):
        """Bundle hasPart detail has no nested archive (handled by bundle wizard)."""
        detail = self._get_distribution_detail()
        hp_detail = detail["elements"][5]["options"]["detail"]
        scopes = [
            el.get("scope") for el in hp_detail["elements"] if el.get("scope")
        ]
        self.assertNotIn("#/properties/schema:hasPart", scopes)

    def test_has_part_image_group(self):
        detail = self._get_distribution_detail()
        hp_detail = detail["elements"][5]["options"]["detail"]
        image_group = hp_detail["elements"][3]
        self.assertEqual(image_group["label"], "Image Details")
        self.assertEqual(image_group["rule"]["effect"], "SHOW")

    def test_has_part_tabular_group(self):
        detail = self._get_distribution_detail()
        hp_detail = detail["elements"][5]["options"]["detail"]
        tabular_group = hp_detail["elements"][4]
        self.assertEqual(tabular_group["label"], "Tabular Data Details")

    def test_has_part_datacube_group(self):
        detail = self._get_distribution_detail()
        hp_detail = detail["elements"][5]["options"]["detail"]
        cube_group = hp_detail["elements"][5]
        self.assertEqual(cube_group["label"], "Data Cube Details")

    def test_has_part_document_group(self):
        detail = self._get_distribution_detail()
        hp_detail = detail["elements"][5]["options"]["detail"]
        doc_group = hp_detail["elements"][6]
        self.assertEqual(doc_group["label"], "Document Details")

    def test_distribution_element_label_prop(self):
        result = inject_uischema(SAMPLE_UISCHEMA)
        dist_ctrl = result["elements"][6]["elements"][0]
        self.assertEqual(dist_ctrl["options"]["elementLabelProp"], "schema:name")

    def _extract_mime_values_from_rule(self, rule):
        """Extract MIME values from flat OR rule structure.

        Rule is OR of individual {scope, schema: {const: mime}} conditions.
        Same pattern used at both distribution and hasPart levels.
        """
        return [
            cond["schema"]["const"]
            for cond in rule["condition"]["conditions"]
        ]

    def test_image_detail_group(self):
        detail = self._get_distribution_detail()
        image_group = detail["elements"][6]
        self.assertEqual(image_group["type"], "Group")
        self.assertEqual(image_group["label"], "Image Details")
        rule = image_group["rule"]
        self.assertEqual(rule["effect"], "SHOW")
        # Flat OR of const conditions (CzForm can't handle any compound nesting)
        self.assertEqual(rule["condition"]["type"], "OR")
        mime_values = self._extract_mime_values_from_rule(rule)
        self.assertIn("image/tiff", mime_values)

    def test_tabular_detail_group(self):
        detail = self._get_distribution_detail()
        tabular_group = detail["elements"][7]
        self.assertEqual(tabular_group["label"], "Tabular Data Details")
        mime_values = self._extract_mime_values_from_rule(tabular_group["rule"])
        self.assertIn("text/csv", mime_values)

    def test_datacube_detail_group(self):
        detail = self._get_distribution_detail()
        cube_group = detail["elements"][8]
        self.assertEqual(cube_group["label"], "Data Cube Details")
        mime_values = self._extract_mime_values_from_rule(cube_group["rule"])
        self.assertIn("application/x-hdf5", mime_values)

    def test_document_detail_group(self):
        detail = self._get_distribution_detail()
        doc_group = detail["elements"][9]
        self.assertEqual(doc_group["label"], "Document Details")
        mime_values = self._extract_mime_values_from_rule(doc_group["rule"])
        self.assertIn("application/pdf", mime_values)

    def test_file_detail_groups_use_flat_scope(self):
        """File-type groups reference file detail properties with flat scope."""
        detail = self._get_distribution_detail()
        image_group = detail["elements"][6]
        first_ctrl = image_group["elements"][0]
        self.assertTrue(
            first_ctrl["scope"].startswith("#/properties/")
        )
        self.assertNotIn("fileDetail", first_ctrl["scope"])


# ===================================================================
# File type inference tests
# ===================================================================


class FileTypeInferenceTest(TestCase):
    """Test that serializer infers file @type from componentType."""

    def setUp(self):
        self.profile = Profile.objects.create(name="inferTest", schema={})

    def _make_attrs(self, jsonld):
        return {"jsonld": jsonld, "profile": self.profile}

    def test_infers_image_type(self):
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [{
                "schema:name": "img",
                "_distributionType": "Data Download",
                "schema:encodingFormat": "image/tiff",
                "componentType": {"@type": "ada:AIVAImage"},
            }],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertIn("ada:image", dist["@type"])
        self.assertIn("schema:ImageObject", dist["@type"])

    def test_infers_tabular_by_prefix(self):
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [{
                "schema:name": "tab",
                "_distributionType": "Data Download",
                "schema:encodingFormat": "text/csv",
                "componentType": {"@type": "ada:LAFTabular"},
            }],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertIn("ada:tabularData", dist["@type"])
        self.assertIn("schema:Dataset", dist["@type"])

    def test_no_inference_without_component_type(self):
        """No componentType means no file type inference, but dist @type is preserved."""
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [{
                "schema:name": "bare",
                "_distributionType": "Data Download",
                "schema:encodingFormat": "text/csv",
            }],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertEqual(dist["@type"], ["schema:DataDownload"])
        self.assertNotIn("componentType", dist)


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
# Per-profile MIME type filtering tests
# ===================================================================


class ProfileMimeFilterTest(TestCase):
    """Test that MIME type dropdowns are filtered per technique profile."""

    def test_ada_product_gets_all_mimes(self):
        mimes = _get_profile_mime_enum("adaProduct")
        self.assertEqual(mimes, MIME_TYPE_ENUM)

    def test_unknown_profile_gets_all_mimes(self):
        mimes = _get_profile_mime_enum("unknownProfile")
        self.assertEqual(mimes, MIME_TYPE_ENUM)

    def test_none_profile_gets_all_mimes(self):
        mimes = _get_profile_mime_enum(None)
        self.assertEqual(mimes, MIME_TYPE_ENUM)

    def test_ada_xrd_has_csv_and_images(self):
        mimes = _get_profile_mime_enum("adaXRD")
        self.assertIn("text/csv", mimes)
        self.assertIn("image/tiff", mimes)
        self.assertIn("application/pdf", mimes)
        # XRD doesn't support data cubes
        self.assertNotIn("application/x-hdf5", mimes)
        self.assertNotIn("application/x-netcdf", mimes)

    def test_ada_vnmir_has_datacube(self):
        mimes = _get_profile_mime_enum("adaVNMIR")
        self.assertIn("application/x-hdf5", mimes)
        self.assertIn("application/x-netcdf", mimes)
        self.assertIn("text/csv", mimes)

    def test_ada_icpms_has_tabular_and_collection(self):
        mimes = _get_profile_mime_enum("adaICPMS")
        self.assertIn("text/csv", mimes)
        self.assertIn("application/zip", mimes)
        # ICPMS doesn't support images directly
        self.assertNotIn("image/tiff", mimes)

    def test_all_profiles_include_structured_data(self):
        """JSON, XML, YAML are always available regardless of profile."""
        for profile in ["adaXRD", "adaICPMS", "adaVNMIR", "adaEMPA"]:
            mimes = _get_profile_mime_enum(profile)
            self.assertIn("application/json", mimes, f"Missing JSON for {profile}")
            self.assertIn("application/xml", mimes, f"Missing XML for {profile}")
            self.assertIn("application/yaml", mimes, f"Missing YAML for {profile}")

    def test_filtered_enum_preserves_sort_order(self):
        """Filtered MIME list maintains the same order as the master list."""
        mimes = _get_profile_mime_enum("adaXRD")
        master_order = [m for m in MIME_TYPE_ENUM if m in mimes]
        self.assertEqual(mimes, master_order)

    def test_inject_schema_defaults_uses_profile(self):
        """inject_schema_defaults with profile_name filters the MIME enum."""
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA, profile_name="adaXRD")
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        enc_fmt = dist_props["schema:encodingFormat"]
        self.assertIn("text/csv", enc_fmt["enum"])
        self.assertNotIn("application/x-hdf5", enc_fmt["enum"])


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

    def test_encoding_format_string_wrapped_to_array(self):
        """Single string encodingFormat is wrapped back to array for JSON-LD."""
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {
                    "schema:name": "File",
                    "_distributionType": "Data Download",
                    "schema:encodingFormat": "text/csv",
                },
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertEqual(dist["schema:encodingFormat"], ["text/csv"])

    def test_encoding_format_empty_string_removed(self):
        """Empty string encodingFormat is removed entirely."""
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {
                    "schema:name": "File",
                    "_distributionType": "Data Download",
                    "schema:encodingFormat": "",
                },
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertNotIn("schema:encodingFormat", dist)

    def test_encoding_format_array_preserved(self):
        """Array encodingFormat (already correct) is left as-is."""
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {
                    "schema:name": "File",
                    "_distributionType": "Data Download",
                    "schema:encodingFormat": ["text/csv"],
                },
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        dist = attrs["jsonld"]["schema:distribution"][0]
        self.assertEqual(dist["schema:encodingFormat"], ["text/csv"])

    def test_has_part_encoding_format_wrapped(self):
        """hasPart encodingFormat strings are wrapped to arrays on save."""
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {
                    "schema:name": "Archive",
                    "_distributionType": "Data Download",
                    "schema:encodingFormat": "application/zip",
                    "schema:hasPart": [
                        {"schema:name": "data.csv", "schema:encodingFormat": "text/csv"},
                        {"schema:name": "img.tiff", "schema:encodingFormat": "image/tiff"},
                    ],
                },
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        parts = attrs["jsonld"]["schema:distribution"][0]["schema:hasPart"]
        self.assertEqual(parts[0]["schema:encodingFormat"], ["text/csv"])
        self.assertEqual(parts[1]["schema:encodingFormat"], ["image/tiff"])

    def test_has_part_empty_encoding_format_removed(self):
        """hasPart empty encodingFormat strings are removed."""
        from records.serializers import RecordSerializer
        jsonld = {
            "schema:distribution": [
                {
                    "schema:name": "Archive",
                    "_distributionType": "Data Download",
                    "schema:encodingFormat": "application/zip",
                    "schema:hasPart": [
                        {"schema:name": "file", "schema:encodingFormat": ""},
                    ],
                },
            ],
        }
        serializer = RecordSerializer()
        attrs = serializer.validate(self._make_attrs(jsonld))
        part = attrs["jsonld"]["schema:distribution"][0]["schema:hasPart"][0]
        self.assertNotIn("schema:encodingFormat", part)


# ===================================================================
# Versioning / deprecation tests
# ===================================================================


class JsonldEqualTest(TestCase):
    """Unit tests for the _jsonld_equal helper."""

    def test_identical_documents(self):
        from records.serializers import _jsonld_equal
        a = {"schema:name": "Test", "schema:description": "A test"}
        b = {"schema:name": "Test", "schema:description": "A test"}
        self.assertTrue(_jsonld_equal(a, b))

    def test_different_documents(self):
        from records.serializers import _jsonld_equal
        a = {"schema:name": "Test"}
        b = {"schema:name": "Different"}
        self.assertFalse(_jsonld_equal(a, b))

    def test_ignores_at_id(self):
        from records.serializers import _jsonld_equal
        a = {"@id": "id1", "schema:name": "Test"}
        b = {"@id": "id2", "schema:name": "Test"}
        self.assertTrue(_jsonld_equal(a, b))

    def test_ignores_date_modified(self):
        from records.serializers import _jsonld_equal
        a = {"schema:name": "Test", "schema:dateModified": "2025-01-01"}
        b = {"schema:name": "Test", "schema:dateModified": "2025-06-01"}
        self.assertTrue(_jsonld_equal(a, b))

    def test_ignores_subject_of_volatile_fields(self):
        from records.serializers import _jsonld_equal
        a = {
            "schema:name": "Test",
            "schema:subjectOf": {
                "@id": "so1",
                "schema:about": {"@id": "id1"},
                "schema:sdDatePublished": "2025-01-01",
                "schema:maintainer": "Alice",
            },
        }
        b = {
            "schema:name": "Test",
            "schema:subjectOf": {
                "@id": "so2",
                "schema:about": {"@id": "id2"},
                "schema:sdDatePublished": "2025-06-01",
                "schema:maintainer": "Alice",
            },
        }
        self.assertTrue(_jsonld_equal(a, b))

    def test_subject_of_non_volatile_difference(self):
        from records.serializers import _jsonld_equal
        a = {
            "schema:name": "Test",
            "schema:subjectOf": {"schema:maintainer": "Alice"},
        }
        b = {
            "schema:name": "Test",
            "schema:subjectOf": {"schema:maintainer": "Bob"},
        }
        self.assertFalse(_jsonld_equal(a, b))


class NextVersionIdentifierTest(TestCase):
    """Unit tests for _next_version_identifier."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL (ArrayField/GinIndex)")
        self.user = User.objects.create_user(
            username="veruser", password="pass", orcid="0000-0000-0000-0050"
        )
        self.profile = Profile.objects.create(name="verProfile", schema={})

    def test_first_version(self):
        """No existing records → returns _2."""
        from records.serializers import _next_version_identifier
        Record.objects.create(
            profile=self.profile, jsonld={}, identifier="#abc123", owner=self.user
        )
        self.assertEqual(_next_version_identifier("#abc123"), "#abc123_2")

    def test_increments_past_existing(self):
        """Existing _2 → returns _3."""
        from records.serializers import _next_version_identifier
        Record.objects.create(
            profile=self.profile, jsonld={}, identifier="#abc123", owner=self.user
        )
        Record.objects.create(
            profile=self.profile, jsonld={}, identifier="#abc123_2", owner=self.user
        )
        self.assertEqual(_next_version_identifier("#abc123"), "#abc123_3")

    def test_strips_existing_suffix_before_computing(self):
        """Input already has _2 suffix → still computes from base."""
        from records.serializers import _next_version_identifier
        Record.objects.create(
            profile=self.profile, jsonld={}, identifier="#abc123", owner=self.user
        )
        Record.objects.create(
            profile=self.profile, jsonld={}, identifier="#abc123_2", owner=self.user
        )
        self.assertEqual(_next_version_identifier("#abc123_2"), "#abc123_3")


class RecordVersioningTest(TestCase):
    """Integration tests for create() versioning logic."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL (ArrayField/GinIndex)")
        self.user = User.objects.create_user(
            username="versionuser", password="pass", orcid="0000-0000-0000-0051"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", password="pass", orcid="0000-0000-0000-0052"
        )
        self.profile = Profile.objects.create(name="versionProfile", schema={})
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _make_jsonld(self, name="Test Dataset", extra_field=None):
        doc = {
            "@id": "#hash123",
            "schema:name": name,
            "schema:subjectOf": {
                "@id": "so1",
                "schema:about": {"@id": "#hash123"},
                "schema:sdDatePublished": "2025-01-01",
            },
        }
        if extra_field:
            doc["schema:description"] = extra_field
        return doc

    def test_identical_reimport_returns_existing(self):
        """Re-importing identical JSON-LD returns the same record, no new version."""
        jsonld = self._make_jsonld()
        resp1 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": jsonld},
            format="json",
        )
        self.assertEqual(resp1.status_code, 201)
        record1_id = resp1.json()["id"]

        # Re-import same data
        resp2 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld()},
            format="json",
        )
        self.assertEqual(resp2.status_code, 201)
        record2_id = resp2.json()["id"]

        # Should be the same record
        self.assertEqual(record1_id, record2_id)
        self.assertEqual(Record.objects.count(), 1)

    def test_different_reimport_deprecates_old(self):
        """Re-importing changed JSON-LD deprecates the old record and creates a new one."""
        resp1 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld()},
            format="json",
        )
        self.assertEqual(resp1.status_code, 201)
        record1_id = resp1.json()["id"]

        # Re-import with different data
        resp2 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld(extra_field="new description")},
            format="json",
        )
        self.assertEqual(resp2.status_code, 201)
        record2_id = resp2.json()["id"]

        # Should be different records
        self.assertNotEqual(record1_id, record2_id)
        self.assertEqual(Record.objects.count(), 2)

        # Old record should be deprecated
        old_record = Record.objects.get(pk=record1_id)
        self.assertEqual(old_record.status, "deprecated")

        # New record should have versioned identifier
        new_record = Record.objects.get(pk=record2_id)
        self.assertEqual(new_record.identifier, "#hash123_2")
        self.assertEqual(new_record.status, "draft")

    def test_versioned_record_updates_jsonld_id(self):
        """New versioned record has @id and subjectOf.about updated."""
        self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld()},
            format="json",
        )
        resp2 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld(extra_field="changed")},
            format="json",
        )
        new_record = Record.objects.get(pk=resp2.json()["id"])
        self.assertEqual(new_record.jsonld["@id"], "#hash123_2")
        self.assertEqual(
            new_record.jsonld["schema:subjectOf"]["schema:about"],
            {"@id": "#hash123_2"},
        )

    def test_third_version_increments(self):
        """Three successive imports with changes produce _2 then _3."""
        self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld()},
            format="json",
        )
        self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld(extra_field="v2")},
            format="json",
        )
        resp3 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld(extra_field="v3")},
            format="json",
        )
        new_record = Record.objects.get(pk=resp3.json()["id"])
        self.assertEqual(new_record.identifier, "#hash123_3")
        # Two deprecated + one active
        self.assertEqual(Record.objects.filter(status="deprecated").count(), 2)
        self.assertEqual(Record.objects.filter(status="draft").count(), 1)

    def test_different_user_gets_fresh_uuid(self):
        """Another user importing the same identifier gets a fresh UUID, not versioning."""
        self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld()},
            format="json",
        )
        # Switch to other user
        self.client.force_authenticate(user=self.other_user)
        resp2 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld()},
            format="json",
        )
        self.assertEqual(resp2.status_code, 201)
        new_record = Record.objects.get(pk=resp2.json()["id"])
        # Should NOT be #hash123 or #hash123_2
        self.assertNotEqual(new_record.identifier, "#hash123")
        self.assertNotIn("_2", new_record.identifier)
        # Original record not deprecated
        self.assertEqual(Record.objects.filter(status="deprecated").count(), 0)

    def test_create_stamps_sd_date_published(self):
        """New record gets schema:sdDatePublished set to current time."""
        jsonld = self._make_jsonld()
        resp = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": jsonld},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        record = Record.objects.get(pk=resp.json()["id"])
        sd = record.jsonld.get("schema:subjectOf", {})
        self.assertIn("schema:sdDatePublished", sd)
        # Should be a valid ISO timestamp
        self.assertIn("T", sd["schema:sdDatePublished"])

    def test_versioned_record_stamps_sd_date_published(self):
        """Versioned record gets a fresh sdDatePublished."""
        self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld()},
            format="json",
        )
        resp2 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": self._make_jsonld(extra_field="v2")},
            format="json",
        )
        new_record = Record.objects.get(pk=resp2.json()["id"])
        sd = new_record.jsonld.get("schema:subjectOf", {})
        self.assertIn("schema:sdDatePublished", sd)


class RecordUpdateConflictTest(TestCase):
    """Integration tests for update() identifier conflict handling."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL (ArrayField/GinIndex)")
        self.user = User.objects.create_user(
            username="updateuser", password="pass", orcid="0000-0000-0000-0053"
        )
        self.profile = Profile.objects.create(name="updateProfile", schema={})
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_update_does_not_change_identifier(self):
        """Update preserves original identifier even when jsonld @id differs.

        Identifier conflict handling was moved to the ADA push flow
        (ada_bridge/services.py _apply_versioning).  Regular save/update
        must never mutate identifiers.
        """
        resp1 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": {"@id": "#aaa", "schema:name": "First"}},
            format="json",
        )
        resp2 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": {"@id": "#bbb", "schema:name": "Second"}},
            format="json",
        )
        record2_id = resp2.json()["id"]

        # Update record2's jsonld to have identifier #aaa (conflicts with record1)
        resp3 = self.client.patch(
            f"/api/catalog/records/{record2_id}/",
            {"jsonld": {
                "@id": "#aaa",
                "schema:name": "Second Updated",
                "schema:subjectOf": {"schema:about": {"@id": "#aaa"}},
            }},
            format="json",
        )
        self.assertEqual(resp3.status_code, 200)

        # Record1 should NOT be deprecated (update doesn't touch other records)
        record1 = Record.objects.get(pk=resp1.json()["id"])
        self.assertEqual(record1.status, "draft")

        # Record2 keeps its original identifier
        record2 = Record.objects.get(pk=record2_id)
        self.assertEqual(record2.identifier, "#bbb")

    def test_update_no_conflict_keeps_identifier(self):
        """Normal update without conflict preserves the identifier."""
        resp1 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": {"@id": "#solo", "schema:name": "Solo"}},
            format="json",
        )
        record_id = resp1.json()["id"]

        resp2 = self.client.patch(
            f"/api/catalog/records/{record_id}/",
            {"jsonld": {"@id": "#solo", "schema:name": "Solo Updated"}},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)
        record = Record.objects.get(pk=record_id)
        self.assertEqual(record.identifier, "#solo")
        self.assertEqual(Record.objects.filter(status="deprecated").count(), 0)

    def test_update_stamps_sd_date_published(self):
        """Updating a record sets sdDatePublished to current time."""
        resp1 = self.client.post(
            "/api/catalog/records/",
            {"profile": self.profile.pk, "jsonld": {
                "@id": "#ts",
                "schema:name": "Timestamp Test",
                "schema:subjectOf": {"schema:about": {"@id": "#ts"}},
            }},
            format="json",
        )
        record_id = resp1.json()["id"]

        resp2 = self.client.patch(
            f"/api/catalog/records/{record_id}/",
            {"jsonld": {
                "@id": "#ts",
                "schema:name": "Timestamp Updated",
                "schema:subjectOf": {"schema:about": {"@id": "#ts"}},
            }},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)
        record = Record.objects.get(pk=record_id)
        sd = record.jsonld.get("schema:subjectOf", {})
        self.assertIn("schema:sdDatePublished", sd)
        self.assertIn("T", sd["schema:sdDatePublished"])


class ExcludeStatusFilterTest(TestCase):
    """Tests for the exclude_status query parameter on the records list."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL (ArrayField/GinIndex)")
        self.user = User.objects.create_user(
            username="filteruser", password="pass", orcid="0000-0000-0000-0054"
        )
        self.profile = Profile.objects.create(name="filterProfile", schema={})
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create records in different statuses
        Record.objects.create(
            profile=self.profile, jsonld={}, identifier="rec-draft",
            owner=self.user, status="draft",
        )
        Record.objects.create(
            profile=self.profile, jsonld={}, identifier="rec-deprecated",
            owner=self.user, status="deprecated",
        )

    def test_exclude_deprecated(self):
        resp = self.client.get("/api/catalog/records/", {"exclude_status": "deprecated"})
        self.assertEqual(resp.status_code, 200)
        identifiers = [r["identifier"] for r in resp.json()["results"]]
        self.assertIn("rec-draft", identifiers)
        self.assertNotIn("rec-deprecated", identifiers)

    def test_no_exclude_returns_all(self):
        resp = self.client.get("/api/catalog/records/")
        self.assertEqual(resp.status_code, 200)
        identifiers = [r["identifier"] for r in resp.json()["results"]]
        self.assertIn("rec-draft", identifiers)
        self.assertIn("rec-deprecated", identifiers)


# ===================================================================
# Profile-specific MIME and componentType filtering tests
# ===================================================================


class GeneratedProfileMimeFilterTest(TestCase):
    """MIME filtering for generated (non-original-4) profiles."""

    def test_ada_dsc_tabular_only_no_image_mimes(self):
        """adaDSC has only tabular types — no image or datacube MIMEs."""
        mimes = _get_profile_mime_enum("adaDSC")
        self.assertIn("text/csv", mimes)
        self.assertIn("text/tab-separated-values", mimes)
        self.assertIn("application/pdf", mimes)  # document always
        self.assertIn("application/zip", mimes)  # collection always
        self.assertNotIn("image/tiff", mimes)
        self.assertNotIn("application/x-hdf5", mimes)

    def test_ada_l2ms_datacube_and_image(self):
        """adaL2MS has datacube + image types — includes both MIME categories."""
        mimes = _get_profile_mime_enum("adaL2MS")
        self.assertIn("application/x-hdf5", mimes)
        self.assertIn("application/x-netcdf", mimes)
        self.assertIn("image/tiff", mimes)
        self.assertIn("image/png", mimes)
        self.assertIn("application/pdf", mimes)

    def test_ada_sem_all_categories(self):
        """adaSEM has image + tabular + datacube types — all MIME categories."""
        mimes = _get_profile_mime_enum("adaSEM")
        self.assertIn("image/tiff", mimes)
        self.assertIn("text/csv", mimes)
        self.assertIn("application/x-hdf5", mimes)
        self.assertIn("application/pdf", mimes)
        self.assertIn("application/zip", mimes)

    def test_ada_dsc_includes_structured_data(self):
        mimes = _get_profile_mime_enum("adaDSC")
        for mime in STRUCTURED_DATA_MIMES:
            self.assertIn(mime, mimes, f"Missing {mime} for adaDSC")

    def test_ada_laf_tabular_only(self):
        """adaLAF has only tabular types."""
        mimes = _get_profile_mime_enum("adaLAF")
        self.assertIn("text/csv", mimes)
        self.assertNotIn("image/tiff", mimes)
        self.assertNotIn("application/x-hdf5", mimes)


class ComponentTypeDropdownFilterTest(TestCase):
    """componentType dropdown filtering per profile."""

    def test_ada_dsc_image_dropdown_generic_only(self):
        """adaDSC has no image types — image dropdown shows only generics."""
        result = _get_profile_category_components("adaDSC", IMAGE_COMPONENT_TYPES)
        non_generic = [t for t in result if t not in GENERIC_COMPONENT_TYPES]
        self.assertEqual(non_generic, [])
        # Generics are present
        self.assertIn("ada:other", result)

    def test_ada_dsc_tabular_dropdown_has_dsc_types(self):
        """adaDSC tabular dropdown shows DSC types + generics."""
        result = _get_profile_category_components("adaDSC", TABULAR_COMPONENT_TYPES)
        self.assertIn("ada:DSCHeatTabular", result)
        self.assertIn("ada:DSCResultsTabular", result)
        self.assertIn("ada:other", result)
        # Should NOT have types from other profiles
        self.assertNotIn("ada:LAFProcessed", result)

    def test_ada_sem_image_dropdown_has_sem_types(self):
        """adaSEM image dropdown shows SEM image types + generics."""
        result = _get_profile_category_components("adaSEM", IMAGE_COMPONENT_TYPES)
        self.assertIn("ada:SEMImageCollection", result)
        self.assertIn("ada:SEMImageMap", result)
        self.assertIn("ada:SEMEBSDGrainImage", result)
        self.assertIn("ada:SEMHRCLImage", result)
        # Should NOT have other profile image types
        self.assertNotIn("ada:AIVAImage", result)
        self.assertNotIn("ada:EMPAImage", result)

    def test_ada_product_full_lists(self):
        """adaProduct gets all types + generics (no filtering)."""
        result = _get_profile_category_components("adaProduct", IMAGE_COMPONENT_TYPES)
        self.assertEqual(result, IMAGE_COMPONENT_TYPES + GENERIC_COMPONENT_TYPES)

    def test_unknown_profile_full_lists(self):
        """Unknown profile gets all types + generics (no filtering)."""
        result = _get_profile_category_components("unknownProfile", TABULAR_COMPONENT_TYPES)
        self.assertEqual(result, TABULAR_COMPONENT_TYPES + GENERIC_COMPONENT_TYPES)

    def test_generics_always_appended(self):
        """All profiles get GENERIC_COMPONENT_TYPES appended."""
        for profile in ["adaDSC", "adaSEM", "adaLAF", "adaProduct"]:
            result = _get_profile_category_components(profile, IMAGE_COMPONENT_TYPES)
            for g in GENERIC_COMPONENT_TYPES:
                self.assertIn(g, result, f"Missing {g} for {profile}")


class InjectSchemaComponentTypeFilterTest(TestCase):
    """Verify inject_schema_defaults filters componentType enums per profile."""

    def test_tabular_enum_filtered_for_technique_profile(self):
        """adaDSC _tabularComponentType enum contains DSC types but not LAF types."""
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA, profile_name="adaDSC")
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        enum = dist_props["_tabularComponentType"]["enum"]
        self.assertIn("ada:DSCHeatTabular", enum)
        self.assertIn("ada:DSCResultsTabular", enum)
        self.assertNotIn("ada:LAFProcessed", enum)
        # Generics present
        self.assertIn("ada:other", enum)

    def test_has_part_component_type_also_filtered(self):
        """hasPart-level _tabularComponentType is also filtered."""
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA, profile_name="adaDSC")
        hp_props = (
            result["properties"]["schema:distribution"]["items"]["properties"]
            ["schema:hasPart"]["items"]["properties"]
        )
        enum = hp_props["_tabularComponentType"]["enum"]
        self.assertIn("ada:DSCHeatTabular", enum)
        self.assertNotIn("ada:LAFProcessed", enum)

    def test_ada_product_gets_full_enum(self):
        """adaProduct _tabularComponentType contains all tabular types."""
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA, profile_name="adaProduct")
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        enum = dist_props["_tabularComponentType"]["enum"]
        self.assertEqual(enum, TABULAR_COMPONENT_TYPES + GENERIC_COMPONENT_TYPES)

    def test_image_enum_empty_for_tabular_only_profile(self):
        """adaDSC _imageComponentType has only generics (no DSC image types)."""
        result = inject_schema_defaults(DISTRIBUTION_SCHEMA, profile_name="adaDSC")
        dist_props = result["properties"]["schema:distribution"]["items"]["properties"]
        enum = dist_props["_imageComponentType"]["enum"]
        non_generic = [t for t in enum if t not in GENERIC_COMPONENT_TYPES]
        self.assertEqual(non_generic, [])


class BackwardCompatProfileMimeTest(TestCase):
    """Backward compat: original 4 profiles produce equivalent MIME lists."""

    def _mime_set(self, profile):
        return set(_get_profile_mime_enum(profile))

    def test_ada_empa_includes_image_tabular_document(self):
        mimes = self._mime_set("adaEMPA")
        self.assertTrue(set(IMAGE_MIMES).issubset(mimes))
        self.assertTrue(set(TABULAR_MIMES).issubset(mimes))
        self.assertTrue(set(DOCUMENT_MIMES).issubset(mimes))
        self.assertIn("application/zip", mimes)
        # EMPA has no datacube types
        self.assertNotIn("application/x-hdf5", mimes)

    def test_ada_xrd_includes_image_tabular_document(self):
        mimes = self._mime_set("adaXRD")
        self.assertTrue(set(IMAGE_MIMES).issubset(mimes))
        self.assertTrue(set(TABULAR_MIMES).issubset(mimes))
        self.assertTrue(set(DOCUMENT_MIMES).issubset(mimes))
        # XRD has no datacube types
        self.assertNotIn("application/x-hdf5", mimes)

    def test_ada_icpms_includes_tabular_collection_document(self):
        mimes = self._mime_set("adaICPMS")
        self.assertTrue(set(TABULAR_MIMES).issubset(mimes))
        self.assertTrue(set(DOCUMENT_MIMES).issubset(mimes))
        self.assertIn("application/zip", mimes)
        # ICPMS has no image types
        self.assertNotIn("image/tiff", mimes)

    def test_ada_vnmir_includes_tabular_image_datacube_document(self):
        mimes = self._mime_set("adaVNMIR")
        self.assertTrue(set(TABULAR_MIMES).issubset(mimes))
        self.assertTrue(set(IMAGE_MIMES).issubset(mimes))
        self.assertTrue(set(DATACUBE_MIMES).issubset(mimes))
        self.assertTrue(set(DOCUMENT_MIMES).issubset(mimes))

    def test_all_original_profiles_include_structured_data(self):
        for profile in ["adaEMPA", "adaXRD", "adaICPMS", "adaVNMIR"]:
            mimes = self._mime_set(profile)
            for mime in STRUCTURED_DATA_MIMES:
                self.assertIn(mime, mimes, f"Missing {mime} for {profile}")


# ---------------------------------------------------------------------------
# Profile detection tests
# ---------------------------------------------------------------------------

from records.profile_detection import detect_profile


class ProfileDetectionTest(TestCase):
    """Tests for the detect_profile() utility and the detect-profile API endpoint."""

    def test_conformsto_detection(self):
        """conformsTo URI should be the highest-priority detection method."""
        jsonld = {
            "schema:subjectOf": {
                "dcterms:conformsTo": [
                    {"@id": "ada:profile/adaSEM"}
                ]
            }
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaSEM")
        self.assertEqual(result["source"], "conformsTo")

    def test_conformsto_full_url(self):
        """Full URL conformsTo should also be detected."""
        jsonld = {
            "schema:subjectOf": {
                "dcterms:conformsTo": [
                    {"@id": "https://ada.astromat.org/metadata/profile/adaEMPA"}
                ]
            }
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaEMPA")
        self.assertEqual(result["source"], "conformsTo")

    def test_conformsto_string_entry(self):
        """conformsTo may be a bare string instead of an object."""
        jsonld = {
            "schema:subjectOf": {
                "dcterms:conformsTo": "ada:profile/adaXRD"
            }
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaXRD")
        self.assertEqual(result["source"], "conformsTo")

    def test_additional_type_ada_prefix(self):
        """ada:-prefixed product types should detect the correct profile."""
        jsonld = {
            "schema:additionalType": ["ada:DataDeliveryPackage", "ada:EMPAImage"]
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaEMPA")
        self.assertEqual(result["source"], "additionalType")

    def test_additional_type_human_readable_label(self):
        """Human-readable technique labels should detect the correct profile."""
        jsonld = {
            "schema:additionalType": ["Scanning electron microscopy"]
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaSEM")
        self.assertEqual(result["source"], "additionalType")

    def test_termcode_fallback(self):
        """termCode should be detected when conformsTo and additionalType don't match."""
        jsonld = {
            "schema:measurementTechnique": {
                "schema:termCode": "XRD"
            }
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaXRD")
        self.assertEqual(result["source"], "termCode")

    def test_no_match_returns_none(self):
        """Empty/unrecognized JSON-LD should return profile: None."""
        result = detect_profile({})
        self.assertIsNone(result["profile"])
        self.assertIsNone(result["source"])

    def test_priority_conformsto_over_additional_type(self):
        """conformsTo should take priority over additionalType."""
        jsonld = {
            "schema:subjectOf": {
                "dcterms:conformsTo": [
                    {"@id": "ada:profile/adaSEM"}
                ]
            },
            "schema:additionalType": ["ada:EMPAImage"],
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaSEM")
        self.assertEqual(result["source"], "conformsTo")

    def test_priority_additional_type_over_termcode(self):
        """additionalType should take priority over termCode."""
        jsonld = {
            "schema:additionalType": ["ada:SEMImageCollection"],
            "schema:measurementTechnique": {
                "schema:termCode": "XRD"
            }
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaSEM")
        self.assertEqual(result["source"], "additionalType")

    def test_additional_type_string_not_list(self):
        """additionalType may be a string instead of a list."""
        jsonld = {
            "schema:additionalType": "ada:VNMIRSpectralPoint"
        }
        result = detect_profile(jsonld)
        self.assertEqual(result["profile"], "adaVNMIR")
        self.assertEqual(result["source"], "additionalType")

    def test_api_endpoint(self):
        """POST /api/catalog/detect-profile/ should return detected profile."""
        Profile.objects.create(name="adaSEM")
        client = APIClient()
        resp = client.post(
            "/api/catalog/detect-profile/",
            data={
                "jsonld": {
                    "schema:additionalType": ["ada:SEMImageCollection"]
                }
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["profile"], "adaSEM")
        self.assertEqual(resp.data["source"], "additionalType")

    def test_api_endpoint_no_jsonld(self):
        """Missing jsonld field should return 400."""
        client = APIClient()
        resp = client.post("/api/catalog/detect-profile/", data={}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_api_endpoint_profile_not_in_db(self):
        """Detected profile that doesn't exist in DB should return None."""
        # Don't create the profile in DB
        client = APIClient()
        resp = client.post(
            "/api/catalog/detect-profile/",
            data={
                "jsonld": {
                    "schema:additionalType": ["ada:SEMImageCollection"]
                }
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["profile"])
