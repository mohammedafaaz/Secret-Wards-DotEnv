"""Frozen synthetic multilingual detection benchmark; independent of organizer data."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.v2.model_runtime import CandidateModels
from sheild.engine import run_pipeline

FIXTURE = ROOT / "evaluation" / "data" / "multilingual_holdout.json"
SEED = 260211
TEMPLATES = {
    "en": [
        "Client name: {patient}; next of kin: {relative}; residence is {location}. BP 118/76; Metformin 500 mg; Dr. Renu Sethi reviewed.",
        "Registration: {patient}\nSpouse: {relative}\nHome address: {location}\nGlucose 94 mg/dL; Dr. Kiran Malik reviewed.",
        "Patient name: {patient}; contact person: {relative}; lives at {location}. Pulse 72 bpm; Aspirin 75 mg.",
        "Subject name: {patient}; sister: {relative}; entered from {location}. Temperature 37 C; Metformin 500 mg.",
        "Beneficiary: {patient}; Father name: {relative}; Street address: {location}. BP 120/80; Dr. Renu Sethi reviewed.",
        "The patient {patient} was accompanied by her spouse {relative}; she resides at {location}. HbA1c 6.1%; Metformin 500 mg.",
        "Patient: {patient}\nD/o: {relative}\nAddress: {location}\nOxygen saturation 98%; BP 118/76.",
        "Patient {patient} arrived with her caregiver {relative}. Home is {location}. Pulse 72 bpm; Dr. Kiran Malik reviewed.",
    ],
    "hi": [
        "पंजीकरण: {patient}; परिजन: {relative}; निवास स्थल: {location}। बीपी 118/76; मेटफॉर्मिन 500 mg; Dr. Renu Sethi ने समीक्षा की।",
        "रोगी: {patient}; पुत्री: {relative}; घर का पता: {location}। नाड़ी 72 bpm; मेटफॉर्मिन 500 mg।",
        "नाम: {patient}; माता का नाम: {relative}; पता: {location}। ग्लूकोज़ 94 mg/dL; Dr. Kiran Malik।",
        "मरीज {patient} के साथ बहन {relative} आईं; निवास: {location}। नाड़ी 72 bpm; दवा 5 mg।",
        "रजिस्ट्रेशन: {patient}; भाई: {relative}; घर: {location}। रक्तचाप 120/80; मेटफॉर्मिन 500 mg।",
        "मरीज: {patient}\nपिता: {relative}\nग्राम: {location}\nतापमान 37 C; बीपी 118/76।",
        "रोगी {patient} को परिजन {relative} लाए; घर का पता: {location}। ग्लूकोज़ 94 mg/dL; दवा 5 mg।",
        "नाम: {patient}; साथी: {relative}; निवास स्थल: {location}। नाड़ी 72 bpm; Dr. Renu Sethi।",
    ],
    "hinglish": [
        "Patient name: {patient}; wife: {relative}; ghar: {location}. BP 118/76; Metformin 500 mg; Dr. Renu Sethi reviewed.",
        "Registration: {patient}; papa: {relative}; home address: {location}. Glucose 94 mg/dL; Dr. Kiran Malik.",
        "Patient {patient} ko sister {relative} laaye; Pata: {location}. Pulse 72 bpm; Aspirin 75 mg.",
        "Name: {patient}; W/o: {relative}; address: {location}. BP 120/80; Metformin 500 mg.",
        "Client name: {patient}; contact person: {relative}; residence is {location}. HbA1c 6.1%; Dr. Renu Sethi.",
        "Patient {patient} with spouse {relative}; she lives at {location}. Pulse 72 bpm; Metformin 500 mg.",
        "Patient: {patient}; father name: {relative}; entered from {location}. Temperature 37 C; Dr. Kiran Malik.",
        "Naam: {patient}; relative name: {relative}; ghar: {location}. BP 118/76; Metformin 500 mg.",
    ],
}
NAME_PARTS = {
    "en": (
        ("Aver", "Beli", "Cavi", "Deli", "Evari", "Faro", "Gavi", "Hali", "Iren", "Javi", "Keli", "Lumi", "Maro", "Neli", "Ovi", "Pavi", "Qori", "Reni", "Seli", "Tavi", "Umi", "Veli", "Waro", "Xeni", "Yaro", "Zeli"),
        ("Dovek", "Mavor", "Selvik", "Torlen", "Vessan", "Quorin", "Belvar", "Norell", "Keldan", "Ravik", "Melvor", "Tavren", "Lorvik", "Sernol", "Delmar", "Voran", "Kelmir", "Nolven", "Rilvek", "Sovran", "Feldan", "Varell", "Mireth", "Tovren", "Lenvor", "Darell"),
        ("Amber", "Banyan", "Cedar", "Dawn", "Elm", "Fern", "Garnet", "Hazel", "Iris", "Juniper", "Kestrel", "Lotus", "Maple", "Nectar", "Olive", "Pine", "Quartz", "Rose", "Saffron", "Tamarind", "Umber", "Violet", "Willow", "Xenia", "Yarrow", "Zinnia"),
        ("Mews", "Court", "Lane", "Grove", "Bend", "Row", "Walk", "Rise"),
    ),
    "hi": (
        ("किवा", "तवि", "निरा", "सवेन", "लिरे", "मिवा", "रुवि", "वेनु", "जिवा", "पिरे", "दुवि", "शिरे", "अवे", "भिरा", "लोवि", "यवे", "हिवा", "चिरे", "गुवि", "फेना", "रेवा", "नीवि", "ओविर", "करे"),
        ("वोरन", "निलव", "तोरिन", "सेलव", "मिरोन", "देलर", "केलव", "राविन", "वेलोर", "नाविर", "लिरोन", "दोरव", "सोरिल", "कावेन", "रुवन", "तेलव", "मोरिन", "निवोर", "पेलव", "शाविर", "गेलोन", "तिरव", "कुलन", "वेथर"),
        ("चमेली", "रागवन", "नीलकमल", "कुंज", "अमलतास", "मोरपंख", "केसर", "गुलमोहर", "पीपल", "चंद्रवन", "बेला", "सूरज"),
        ("पथ", "चौक", "गली", "आंगन", "मार्ग", "कुंज", "विहार", "नगर"),
    ),
    "hinglish": (
        ("Nivara", "Tavira", "Kivela", "Soreva", "Mireli", "Vireya", "Lunavi", "Pavira", "Rilena", "Dovira", "Senavi", "Kelira", "Toravi", "Nareli", "Juvina", "Harela", "Yuvira", "Belira", "Zoreva", "Gavira", "Evelin", "Farela", "Ovelia", "Wenira"),
        ("Norrin", "Vossel", "Toran", "Luvak", "Senol", "Dovek", "Vana", "Meloth", "Keldon", "Ravell", "Nolen", "Veldan", "Tovren", "Darell", "Mavik", "Sorell", "Korin", "Velmir", "Neroth", "Selvar", "Teren", "Lorin", "Mireth", "Dovran"),
        ("Gulmohar", "Kesar", "Neelkamal", "Amaltas", "MorPankh", "Banyan", "Chand", "Peacock", "SilverFern", "Violet", "Juniper", "Marigold"),
        ("Gali", "Bagh Road", "Chowk", "Lane", "Colony", "Mews", "Bend", "Path"),
    ),
}


def _name(lang: str, rng: random.Random) -> str:
    given, family, _, _ = NAME_PARTS[lang]
    return f"{rng.choice(given)} {rng.choice(family)}"


def _location(lang: str, rng: random.Random) -> str:
    _, _, first, endings = NAME_PARTS[lang]
    return f"{rng.choice(first)} {rng.choice(endings)}"


def generate() -> list[dict]:
    records = []
    for offset, lang in enumerate(TEMPLATES):
        rng = random.Random(SEED + offset)
        used = set()
        for index in range(120):
            patient = _name(lang, rng)
            relative = _name(lang, rng)
            while patient == relative or patient in used or relative in used:
                patient = _name(lang, rng)
                relative = _name(lang, rng)
            used.update((patient, relative))
            location = _location(lang, rng)
            template = TEMPLATES[lang][index % len(TEMPLATES[lang])]
            clinical = ["118/76", "Metformin 500 mg", "Dr. Renu Sethi"]
            if lang == "hi":
                clinical = ["120/80", "मेटफॉर्मिन 500 mg", "Dr. Renu Sethi"]
            text = template.format(patient=patient, relative=relative, location=location)
            records.append({
                "id": f"{lang}-{index:03d}",
                "language": lang,
                "partition": "development" if index < 20 else "frozen-evaluation",
                "text": text,
                "pii": {"patient": patient, "relative": relative, "location": location},
                "clinical": clinical,
            })
    return records


def _run(records: list[dict], model: CandidateModels | None) -> dict[str, str]:
    output: dict[str, bytes] = {}
    entries = [(f"{item['id']}.txt", item["text"].encode("utf-8")) for item in records]
    report, _ = run_pipeline(entries, output, "independent-multilingual-evaluation", model)
    paths = {item["input_sha256"]: item["output"] for item in report["files"] if item.get("output")}
    return {
        item["id"]: output[paths[hashlib.sha256(item["text"].encode("utf-8")).hexdigest()]].decode("utf-8")
        for item in records
    }


def _crf_output(text: str, model: CandidateModels) -> str:
    spans = [span for span in model.spans(text) if span["label"] != "CLINICAL"]
    for span in sorted(spans, key=lambda item: item["start"], reverse=True):
        text = text[:span["start"]] + "[CRF_REDACTED]" + text[span["end"]:]
    return text


def _score(records: list[dict], outputs: dict[str, dict[str, str]]) -> dict:
    result = {}
    for mode, by_id in outputs.items():
        counts = defaultdict(lambda: {"pii_total": 0, "pii_removed": 0, "clinical_total": 0, "clinical_kept": 0})
        false_negatives = []
        false_positive_probes = []
        for item in records:
            row = counts[(item["language"], "all")]
            row["pii_total"] += len(item["pii"])
            clinical_probes = [probe for probe in item["clinical"] if probe.casefold() in item["text"].casefold()]
            row["clinical_total"] += len(clinical_probes)
            text = by_id[item["id"]]
            for entity, surface in item["pii"].items():
                entity_row = counts[(item["language"], entity)]
                entity_row["pii_total"] += 1
                removed = surface.casefold() not in text.casefold()
                if removed:
                    row["pii_removed"] += 1
                    entity_row["pii_removed"] += 1
                else:
                    false_negatives.append({"id": item["id"], "entity": entity, "surface": surface})
            for probe in clinical_probes:
                kept = probe.casefold() in text.casefold()
                if kept:
                    row["clinical_kept"] += 1
                else:
                    false_positive_probes.append({"id": item["id"], "surface": probe})
        result[mode] = {
            "by_language_and_entity": {
                f"{lang}_{entity}": {
                    **value,
                    "recall": value["pii_removed"] / value["pii_total"] if value["pii_total"] else None,
                }
                for (lang, entity), value in sorted(counts.items()) if entity != "all"
            },
            "by_language": {
                lang: {
                    **counts[(lang, "all")],
                    "pii_recall": counts[(lang, "all")]["pii_removed"] / counts[(lang, "all")]["pii_total"],
                    "clinical_preservation": counts[(lang, "all")]["clinical_kept"] / counts[(lang, "all")]["clinical_total"],
                }
                for lang in TEMPLATES
            },
            "overall": {
                "notes": len(records),
                "pii_total": sum(counts[(lang, "all")]["pii_total"] for lang in TEMPLATES),
                "pii_removed": sum(counts[(lang, "all")]["pii_removed"] for lang in TEMPLATES),
                "pii_recall": sum(counts[(lang, "all")]["pii_removed"] for lang in TEMPLATES)
                / sum(counts[(lang, "all")]["pii_total"] for lang in TEMPLATES),
                "clinical_total": sum(counts[(lang, "all")]["clinical_total"] for lang in TEMPLATES),
                "clinical_kept": sum(counts[(lang, "all")]["clinical_kept"] for lang in TEMPLATES),
                "clinical_preservation": sum(counts[(lang, "all")]["clinical_kept"] for lang in TEMPLATES)
                / sum(counts[(lang, "all")]["clinical_total"] for lang in TEMPLATES),
                "false_negative_surfaces": len(false_negatives),
                "false_positive_clinical_probes": len(false_positive_probes),
            },
            "false_negatives": false_negatives,
            "false_positive_clinical_probes": false_positive_probes,
        }
    return result


def evaluate() -> dict:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    heldout = [item for item in records if item["partition"] == "frozen-evaluation"]
    if len(heldout) < 300 or len({item["id"] for item in heldout}) != len(heldout):
        raise ValueError("frozen_evaluation_partition_invalid")
    model = CandidateModels()
    outputs = {
        "rules_only": _run(heldout, None),
        "standalone_crf": {item["id"]: _crf_output(item["text"], model) for item in heldout},
        "hybrid": _run(heldout, model),
    }
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    return {
        "scope": "independent synthetic templates; not official hidden data; no organizer practice/training records",
        "fixture_sha256": digest,
        "partition": {"development": 60, "frozen_evaluation": len(heldout)},
        "method": "Each held-out note is processed with its exact annotated PII surfaces and three clinical negative probes. Recall is exact surface absence; false-positive count covers only the annotated protected clinical probes, not all possible false positives.",
        "results": _score(heldout, outputs),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true", help="Write the deterministic 60+300 note fixture")
    parser.add_argument("--output", type=Path, help="Write the evaluation result as UTF-8 JSON")
    args = parser.parse_args()
    if args.freeze:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(generate(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"frozen {FIXTURE} sha256={hashlib.sha256(FIXTURE.read_bytes()).hexdigest()}")
        return
    result = json.dumps(evaluate(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(result, end="")


if __name__ == "__main__":
    main()
