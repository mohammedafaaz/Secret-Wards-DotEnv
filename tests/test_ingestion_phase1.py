import json
import stat
from types import SimpleNamespace

import pytest

from sheild import engine


def _alpha(index):
    return chr(65 + index % 26) + chr(65 + (index // 26) % 26)


def _synthetic_input(index):
    format_index = index % 3
    language_index = index % 3
    phone = f"9{123456789 + index:09d}"
    names = ("Synthetic Patient " + _alpha(index), "कल्पित व्यक्ति " + _alpha(index), "Kalpit Mareez " + _alpha(index))
    name = names[language_index]
    if format_index == 0:
        header = "Patient Name,Mobile,Diagnosis,Medicine\n" if language_index != 1 else "नाम,मोबाइल,Diagnosis,Medicine\n"
        row = f"{name},{phone},Diabetes mellitus,Metformin 500 mg\n"
        text = header + row
        raw = text.encode("utf-16") if index % 10 == 0 else text.encode("utf-8-sig" if index % 10 == 1 else "utf-8")
        return f"synthetic/{index}.csv", raw, name, phone, "Metformin 500 mg"
    if format_index == 1:
        value = {"patient_name": name, "mobile": phone, "diagnosis": "Diabetes mellitus", "medicine": "Metformin 500 mg"}
        raw = json.dumps(value, ensure_ascii=False).encode("utf-16" if index % 10 == 0 else "utf-8-sig" if index % 10 == 1 else "utf-8")
        return f"synthetic/{index}.json", raw, name, phone, "Metformin 500 mg"
    label = "नाम" if language_index == 1 else "Patient Name"
    phone_label = "मोबाइल" if language_index == 1 else "Mobile"
    text = f"{label}: {name}\n{phone_label}: {phone}\nDiagnosis: Diabetes mellitus\nMedicine: Metformin 500 mg\nAddress: 4 Synthetic Road\n"
    raw = text.encode("utf-16") if index % 10 == 0 else text.encode("utf-8-sig" if index % 10 == 1 else "utf-8")
    return f"synthetic/{index}.txt", raw, name, phone, "Metformin 500 mg"


@pytest.mark.parametrize("index", range(100), ids=lambda index: f"synthetic-{index:03d}")
def test_synthetic_multiformat_ingestion_fixtures(index):
    path, raw, name, phone, clinical = _synthetic_input(index)
    output = {}
    report, _ = engine.run_pipeline([(path, raw)], output, "phase1-fixture-secret", None)
    sanitized = next(value.decode("utf-8") for key, value in output.items() if key.startswith("sanitized/"))
    assert report["counts"]["files_sanitized"] == 1
    assert name.casefold() not in sanitized.casefold()
    assert phone not in sanitized
    assert clinical in sanitized


def _bundle():
    def full_url(number):
        return f"urn:uuid:00000000-0000-4000-8000-{number:012d}"

    def entry(number, resource):
        return {"fullUrl": full_url(number), "resource": resource}

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Synthetic Alpha"}], "telecom": [{"system": "phone", "value": "9000000001"}]}),
            entry(2, {"resourceType": "Patient", "id": "p2", "name": [{"text": "Synthetic Beta"}], "telecom": [{"system": "phone", "value": "9000000002"}]}),
            entry(3, {"resourceType": "Organization", "id": "org", "name": "Synthetic Hospital"}),
            entry(4, {"resourceType": "Practitioner", "id": "prac", "name": [{"text": "Dr. Synthetic Clinician"}]}),
            entry(5, {"resourceType": "Encounter", "id": "e1", "status": "finished", "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"}, "subject": {"reference": "Patient/p1"}, "serviceProvider": {"reference": "Organization/org"}}),
            entry(6, {"resourceType": "Encounter", "id": "e2", "status": "finished", "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"}, "subject": {"reference": "Patient/p2"}, "serviceProvider": {"reference": "Organization/org"}}),
            entry(7, {"resourceType": "Observation", "id": "o1", "status": "final", "code": {"text": "Pulse"}, "subject": {"reference": "Patient/p1"}, "encounter": {"reference": "Encounter/e1"}, "valueQuantity": {"value": 72, "unit": "beats/min"}}),
            entry(8, {"resourceType": "Observation", "id": "o2", "status": "final", "code": {"text": "Pulse"}, "subject": {"reference": "Patient/p2"}, "encounter": {"reference": "Encounter/e2"}, "valueQuantity": {"value": 81, "unit": "beats/min"}}),
        ],
    }


def test_multi_patient_bundle_uses_resource_specific_owners_and_keeps_shared_resources():
    source = _bundle()
    raw = json.dumps(source, ensure_ascii=False).encode()
    doc = engine.parse("multi.json", raw)
    assert len(doc.records) == 2
    assert doc.fhir_ownership[4] == 0
    assert doc.fhir_ownership[5] == 1
    assert doc.fhir_ownership[6] == 0
    assert doc.fhir_ownership[7] == 1
    assert 2 not in doc.fhir_ownership
    assert 3 not in doc.fhir_ownership

    output = {}
    report, processed = engine.run_pipeline([("multi.json", raw)], output, "phase1-fhir-secret", None)
    sanitized = json.loads(output[processed[0].output])
    patient_ids = {
        "p1": engine.Engine("phase1-fhir-secret").token("Patient|p1", "R"),
        "p2": engine.Engine("phase1-fhir-secret").token("Patient|p2", "R"),
    }
    references = {
        entry["resource"]["id"]: entry["resource"]["subject"]["reference"]
        for entry in sanitized["entry"]
        if entry["resource"]["resourceType"] == "Observation"
    }
    assert references[engine.Engine("phase1-fhir-secret").token("Observation|o1", "R")] == "Patient/" + patient_ids["p1"]
    assert references[engine.Engine("phase1-fhir-secret").token("Observation|o2", "R")] == "Patient/" + patient_ids["p2"]
    patients = [entry["resource"] for entry in sanitized["entry"] if entry["resource"]["resourceType"] == "Patient"]
    assert {patient["id"] for patient in patients} == set(patient_ids.values())
    assert len({patient["identifier"][-1]["value"] for patient in patients}) == 2
    assert {entry["resource"]["valueQuantity"]["value"] for entry in sanitized["entry"] if entry["resource"]["resourceType"] == "Observation"} == {72, 81}
    encoded = json.dumps(sanitized, ensure_ascii=False)
    for raw_identifier in ("Synthetic Alpha", "Synthetic Beta", "9000000001", "9000000002"):
        assert raw_identifier not in encoded
    assert "Synthetic Hospital" in encoded
    assert "Dr. Synthetic Clinician" in encoded
    assert report["counts"]["records_processed"] == 2
    assert len(patients) == 2


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("missing_subject", "fhir_ownership_missing"),
        ("unresolved_subject", "fhir_ownership_unresolved"),
        ("ambiguous_subject", "fhir_ambiguous_ownership"),
    ],
)
def test_fhir_patient_ownership_failures_are_quarantined(mutation, reason):
    bundle = _bundle()
    observation = bundle["entry"][6]["resource"]
    if mutation == "missing_subject":
        observation.pop("subject")
        observation.pop("encounter")
    elif mutation == "unresolved_subject":
        observation["subject"]["reference"] = "Patient/missing"
        observation.pop("encounter")
    else:
        observation["encounter"]["reference"] = "Encounter/e2"
    with pytest.raises(ValueError, match=reason):
        engine.parse("invalid.json", json.dumps(bundle).encode())


@pytest.mark.parametrize("mutation", ["missing_bundle_type", "missing_observation_status"])
def test_fhir_required_bundle_and_resource_structure_is_rejected(mutation):
    bundle = _bundle()
    if mutation == "missing_bundle_type":
        bundle.pop("type")
    else:
        bundle["entry"][6]["resource"].pop("status")
    with pytest.raises(ValueError, match="fhir_invalid_"):
        engine.parse("invalid-structure.json", json.dumps(bundle).encode())


def test_content_detection_and_csv_delimiter_preserve_structures():
    as_json = engine.parse("record.txt", b'{"patient_name":"Synthetic Name","value":12.5}')
    assert as_json.fmt == ".json"
    bracketed_note = engine.parse("message.txt", b"[09:30] Patient: Synthetic Name\nMetformin 500 mg\n")
    assert bracketed_note.fmt == ".txt"
    assert bracketed_note.data.startswith("[09:30]")
    as_tsv = engine.parse("record.csv", b"Patient Name\tMedicine\nSynthetic Name\tMetformin 500 mg\n")
    assert as_tsv.fmt == ".tsv"
    assert as_tsv.delimiter == "\t"
    assert as_tsv.header == ["Patient Name", "Medicine"]
    assert as_tsv.data == [["Synthetic Name", "Metformin 500 mg"]]


def test_json_clinical_numeric_types_and_boolean_values_are_preserved():
    source = {
        "patient_name": "Synthetic Person",
        "age": 46,
        "result": 120.5,
        "enabled": False,
        "observations": [{"result": 0, "comment": None}],
    }
    output = {}
    _, documents = engine.run_pipeline([("numeric.json", json.dumps(source).encode())], output, "phase1-numeric-secret", None)
    sanitized = json.loads(output[documents[0].output])
    assert sanitized["result"] == 120.5
    assert isinstance(sanitized["result"], float)
    assert sanitized["enabled"] is False
    assert sanitized["observations"] == [{"result": 0, "comment": None}]
    assert sanitized["age"] is None
    assert isinstance(sanitized["age_band"], str)


def test_decode_supports_bom_utf16_and_cp1252_without_replacement():
    assert engine.decode(b"\xff\xfe" + "Patient Name: Synthetic".encode("utf-16-le")) == "Patient Name: Synthetic"
    assert engine.decode(b"caf\xe9") == "café"
    with pytest.raises(ValueError, match="invalid_encoding_marker"):
        engine.decode(b"mixed\xff\xfeencoding")


def test_duplicate_json_keys_and_normalized_csv_headers_are_rejected():
    with pytest.raises(ValueError, match="duplicate_json_key"):
        engine.parse("duplicate.json", b'{"patient_name":"A","patient_name":"B"}')
    with pytest.raises(ValueError, match="duplicate_header"):
        engine.parse("duplicate.csv", b"Patient Name,patient_name\nSynthetic Person,Synthetic Person\n")


def test_run_pipeline_rejects_casefolded_duplicate_paths_and_unsafe_paths():
    output = {}
    report, _ = engine.run_pipeline([("record.txt", b"Clinical note."), ("RECORD.TXT", b"Another note.")], output, "phase1-path-secret", None)
    assert report["files"][1]["reason"] == "duplicate_path"
    unsafe = {}
    unsafe_report, _ = engine.run_pipeline([("../outside.txt", b"Clinical note.")], unsafe, "phase1-path-secret", None)
    assert unsafe_report["files"][0]["reason"] == "unsafe_path"
    assert not any(key.startswith("sanitized/") for key in unsafe)


def test_directory_entries_are_sorted_bounded_and_do_not_follow_symlinks(tmp_path, monkeypatch):
    (tmp_path / "b.txt").write_bytes(b"second")
    (tmp_path / "a.txt").write_bytes(b"first")
    assert list(engine.directory_entries(tmp_path)) == [("a.txt", b"first"), ("b.txt", b"second")]

    linked = tmp_path / "linked.txt"
    linked.write_bytes(b"must not be read")
    original_lstat = type(tmp_path).lstat

    def report_symlink(path):
        if path == linked:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
        return original_lstat(path)

    monkeypatch.setattr(type(tmp_path), "lstat", report_symlink)
    with pytest.raises(ValueError, match="symlink_not_allowed"):
        list(engine.directory_entries(tmp_path))

    bounded = tmp_path / "bounded"
    bounded.mkdir()
    (bounded / "one.txt").write_bytes(b"one")
    (bounded / "two.txt").write_bytes(b"two")
    monkeypatch.setattr(engine, "MAX_FILES", 1)
    with pytest.raises(ValueError, match="dataset_limit"):
        list(engine.directory_entries(bounded))

    directory_limited = tmp_path / "directory-limited"
    directory_limited.mkdir()
    (directory_limited / "one").mkdir()
    (directory_limited / "two").mkdir()
    monkeypatch.setattr(engine, "MAX_DIRECTORIES", 2)
    with pytest.raises(ValueError, match="dataset_limit"):
        list(engine.directory_entries(directory_limited))

    entries_limited = tmp_path / "entries-limited"
    entries_limited.mkdir()
    (entries_limited / "one.txt").write_bytes(b"one")
    (entries_limited / "two.txt").write_bytes(b"two")
    monkeypatch.setattr(engine, "MAX_DIRECTORY_ENTRIES", 1)
    with pytest.raises(ValueError, match="dataset_limit"):
        list(engine.directory_entries(entries_limited))


def _fhir_entry(number, resource, full_url=None):
    return {"fullUrl": full_url or f"urn:uuid:00000000-0000-4000-8000-{number:012d}", "resource": resource}


def _three_patient_bundle():
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Alpha One"}]}),
            _fhir_entry(2, {"resourceType": "Patient", "id": "p2", "name": [{"text": "Beta Two"}]}),
            _fhir_entry(3, {"resourceType": "Patient", "id": "p3", "name": [{"text": "Gamma Three"}]}),
            _fhir_entry(4, {"resourceType": "Organization", "id": "org", "name": "Synthetic Hospital"}),
            _fhir_entry(5, {"resourceType": "Practitioner", "id": "prac", "name": [{"text": "Dr. Synthetic"}]}),
            _fhir_entry(6, {"resourceType": "Encounter", "id": "e1", "status": "finished",
                           "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                           "subject": {"reference": "Patient/p1"}, "serviceProvider": {"reference": "Organization/org"}}),
            _fhir_entry(7, {"resourceType": "Encounter", "id": "e2", "status": "finished",
                           "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                           "subject": {"reference": "Patient/p2"}, "serviceProvider": {"reference": "Organization/org"}}),
            _fhir_entry(8, {"resourceType": "Encounter", "id": "e3", "status": "finished",
                           "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                           "subject": {"reference": "Patient/p3"}, "serviceProvider": {"reference": "Organization/org"}}),
            _fhir_entry(9, {"resourceType": "Observation", "id": "o1", "status": "final",
                           "code": {"text": "Pulse"}, "subject": {"reference": "Patient/p1"},
                           "encounter": {"reference": "Encounter/e1"},
                           "valueQuantity": {"value": 72, "unit": "beats/min"}}),
            _fhir_entry(10, {"resourceType": "Observation", "id": "o2", "status": "final",
                            "code": {"text": "Pulse"}, "subject": {"reference": "Patient/p2"},
                            "encounter": {"reference": "Encounter/e2"},
                            "valueQuantity": {"value": 81, "unit": "beats/min"}}),
            _fhir_entry(11, {"resourceType": "DiagnosticReport", "id": "dr1", "status": "final",
                            "code": {"text": "Blood panel"}, "subject": {"reference": "Patient/p3"},
                            "result": [{"reference": "Observation/o1"}]}),
            _fhir_entry(12, {"resourceType": "RelatedPerson", "id": "rp1", "name": [{"text": "Relative of Alpha"}],
                            "patient": {"reference": "Patient/p1"}}),
            _fhir_entry(13, {"resourceType": "MedicationRequest", "id": "mr1", "status": "active", "intent": "order",
                            "subject": {"reference": "Patient/p2"},
                            "medicationCodeableConcept": {"text": "Metformin 500 mg"}}),
        ],
    }


def test_three_patients_in_one_bundle_preserve_separate_ownership():
    source = _three_patient_bundle()
    raw = json.dumps(source, ensure_ascii=False).encode()
    doc = engine.parse("multi_patient.json", raw)
    assert len(doc.records) == 3
    owners = doc.fhir_ownership
    # Entry indices are 0-based: Patients at entries 0,1,2
    assert owners[0] == 0  # Patient p1 owns itself -> record 0
    assert owners[1] == 1  # Patient p2 owns itself -> record 1
    assert owners[2] == 2  # Patient p3 owns itself -> record 2
    # Encounters at entries 5,6,7 owned by patients
    assert owners[5] in (0, 1, 2)
    assert owners[6] in (0, 1, 2)
    assert owners[7] in (0, 1, 2)
    # Observations at entries 8,9 owned by patients
    assert owners[8] in (0, 1, 2)
    assert owners[9] in (0, 1, 2)
    # DiagnosticReport at entry 10 -> Patient p3 -> record 2
    assert owners[10] == 2
    # RelatedPerson at entry 11 -> Patient p1 -> record 0
    assert owners[11] == 0
    # MedicationRequest at entry 12 -> Patient p2 -> record 1
    assert owners[12] == 1
    # Organization at entry 3 and Practitioner at entry 4 unowned
    assert 3 not in owners and 4 not in owners


def test_three_patient_bundle_output_preserves_clinical_values():
    source = _three_patient_bundle()
    raw = json.dumps(source, ensure_ascii=False).encode()
    output = {}
    _, processed = engine.run_pipeline([("multi_patient.json", raw)], output, "fhir-three-patient-secret", None)
    sanitized = json.loads(output[processed[0].output])
    patient_ids = {}
    for entry in sanitized["entry"]:
        if entry["resource"]["resourceType"] == "Patient":
            patient_ids[entry["resource"]["id"]] = entry["resource"]["id"]
    assert len(patient_ids) == 3
    obs_values = {entry["resource"]["valueQuantity"]["value"]
                  for entry in sanitized["entry"]
                  if entry["resource"]["resourceType"] == "Observation"}
    assert obs_values == {72, 81}
    encoded = json.dumps(sanitized, ensure_ascii=False)
    for raw_name in ("Alpha One", "Beta Two", "Gamma Three"):
        assert raw_name not in encoded
    assert "Synthetic Hospital" in encoded
    assert "Dr. Synthetic" in encoded


def test_related_person_ownership_resolves_to_patient():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Patient One"}]}),
            _fhir_entry(2, {"resourceType": "RelatedPerson", "id": "rp1", "name": [{"text": "Relative One"}],
                            "patient": {"reference": "Patient/p1"}}),
        ],
    }
    doc = engine.parse("related.json", json.dumps(bundle).encode())
    assert len(doc.records) == 1
    # RelatedPerson at entry index 1 owned by Patient record 0
    assert doc.fhir_ownership[1] == 0


def test_diagnostic_report_references_observation():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Patient One"}]}),
            _fhir_entry(2, {"resourceType": "Observation", "id": "o1", "status": "final",
                            "code": {"text": "Glucose"}, "subject": {"reference": "Patient/p1"},
                            "valueQuantity": {"value": 95, "unit": "mg/dL"}}),
            _fhir_entry(3, {"resourceType": "DiagnosticReport", "id": "dr1", "status": "final",
                            "code": {"text": "Metabolic panel"}, "subject": {"reference": "Patient/p1"},
                            "result": [{"reference": "Observation/o1"}]}),
        ],
    }
    doc = engine.parse("report.json", json.dumps(bundle).encode())
    assert len(doc.records) == 1
    # Observation at entry index 1, DiagnosticReport at entry index 2, both owned by Patient record 0
    assert doc.fhir_ownership[1] == 0
    assert doc.fhir_ownership[2] == 0


def test_medication_request_ownership():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Patient One"}]}),
            _fhir_entry(2, {"resourceType": "MedicationRequest", "id": "mr1", "status": "active", "intent": "order",
                            "subject": {"reference": "Patient/p1"},
                            "medicationCodeableConcept": {"text": "Metformin 500 mg"}}),
        ],
    }
    doc = engine.parse("meds.json", json.dumps(bundle).encode())
    assert len(doc.records) == 1
    # MedicationRequest at entry index 1 owned by Patient record 0
    assert doc.fhir_ownership[1] == 0


def test_contained_resources_remapped():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Patient One"}],
                            "contained": [{"resourceType": "AllergyIntolerance", "id": "ai1",
                                           "code": {"text": "Penicillin"}}]}),
        ],
    }
    raw = json.dumps(bundle).encode()
    doc = engine.parse("contained.json", raw)
    assert len(doc.records) == 1


def test_urn_uuid_and_relative_references():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Patient One"}]}),
            _fhir_entry(2, {"resourceType": "Observation", "id": "o1", "status": "final",
                            "code": {"text": "Pulse"}, "subject": {"reference": "urn:uuid:00000000-0000-4000-8000-000000000001"},
                            "valueQuantity": {"value": 72, "unit": "beats/min"}}),
        ],
    }
    raw = json.dumps(bundle).encode()
    doc = engine.parse("urnref.json", raw)
    assert len(doc.records) == 1


def test_conflicting_ownership_quarantined():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Patient One"}]}),
            _fhir_entry(2, {"resourceType": "Patient", "id": "p2", "name": [{"text": "Patient Two"}]}),
            _fhir_entry(3, {"resourceType": "Observation", "id": "o1", "status": "final",
                            "code": {"text": "Pulse"}, "subject": {"reference": "Patient/p1"},
                            "encounter": {"reference": "Encounter/e_shared"},
                            "valueQuantity": {"value": 72, "unit": "beats/min"}}),
            _fhir_entry(4, {"resourceType": "Encounter", "id": "e_shared", "status": "finished",
                            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                            "subject": {"reference": "Patient/p1"}}),
            _fhir_entry(5, {"resourceType": "Encounter", "id": "e_shared", "status": "finished",
                            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                            "subject": {"reference": "Patient/p2"}}),
        ],
    }
    raw = json.dumps(bundle).encode()
    with pytest.raises(ValueError, match="fhir_"):
        engine.parse("conflict.json", raw)


def test_unresolved_patient_reference_quarantined():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Patient One"}]}),
            _fhir_entry(2, {"resourceType": "Observation", "id": "o1", "status": "final",
                            "code": {"text": "Pulse"}, "subject": {"reference": "Patient/missing"},
                            "valueQuantity": {"value": 72, "unit": "beats/min"}}),
        ],
    }
    raw = json.dumps(bundle).encode()
    with pytest.raises(ValueError, match="fhir_ownership_unresolved"):
        engine.parse("unresolved.json", raw)


def test_shared_practitioner_organization_remain_shared():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            _fhir_entry(1, {"resourceType": "Patient", "id": "p1", "name": [{"text": "Patient One"}]}),
            _fhir_entry(2, {"resourceType": "Patient", "id": "p2", "name": [{"text": "Patient Two"}]}),
            _fhir_entry(3, {"resourceType": "Organization", "id": "org", "name": "Shared Hospital"}),
            _fhir_entry(4, {"resourceType": "Practitioner", "id": "prac", "name": [{"text": "Dr. Shared"}]}),
            _fhir_entry(5, {"resourceType": "Encounter", "id": "e1", "status": "finished",
                            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                            "subject": {"reference": "Patient/p1"}, "serviceProvider": {"reference": "Organization/org"}}),
            _fhir_entry(6, {"resourceType": "Encounter", "id": "e2", "status": "finished",
                            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                            "subject": {"reference": "Patient/p2"}, "serviceProvider": {"reference": "Organization/org"}}),
        ],
    }
    doc = engine.parse("shared.json", json.dumps(bundle).encode())
    assert len(doc.records) == 2
    # Entry indices 0-based: Organization at index 2, Practitioner at index 3 are shared (not in ownership)
    assert 2 not in doc.fhir_ownership
    assert 3 not in doc.fhir_ownership
    # Encounters at indices 4,5 owned by patients
    assert doc.fhir_ownership[4] in (0, 1)
    assert doc.fhir_ownership[5] in (0, 1)
