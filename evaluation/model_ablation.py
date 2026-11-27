"""Small hand-authored multilingual detection ablation; not an organizer score."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.v2.model_runtime import CandidateModels
from sheild.engine import run_pipeline

SAMPLES = [
    ("en", "Patient: Kivara Meloth\nFather: Isven Meloth\nAddress: Tamarind Mews. BP 118/76; Metformin 500 mg.", ["Kivara Meloth", "Isven Meloth", "Tamarind Mews"], ["BP 118/76", "Metformin 500 mg"]),
    ("en", "Patient Darela Voskin arrived with her mother; guardian name: Vela Voskin. She lives at Juniper Crescent. Glucose 94 mg/dL.", ["Darela Voskin", "Vela Voskin", "Juniper Crescent"], ["Glucose 94 mg/dL"]),
    ("en", "Name: Pavar Nolen; W/o: Elin Nolen; Address: Cobalt Hill House. Pulse 72 bpm; aspirin 75 mg.", ["Pavar Nolen", "Elin Nolen", "Cobalt Hill House"], ["Pulse 72 bpm", "aspirin 75 mg"]),
    ("en", "The patient Omri Veldane returned for review with father Teren Veldane; residence is Amber Finch Walk. BP 120/80.", ["Omri Veldane", "Teren Veldane", "Amber Finch Walk"], ["BP 120/80"]),
    ("en", "Patient: Arvani Dorell; Relative: Thela Dorell; Pata: Lotus Bank Road. HbA1c 6.2%; metformin 500 mg.", ["Arvani Dorell", "Thela Dorell", "Lotus Bank Road"], ["HbA1c 6.2%", "metformin 500 mg"]),
    ("en", "At follow-up, patient Nivara Keldon spoke with her father Sorev Keldon, who lives at Pale Willow Court. Temperature 37 C.", ["Nivara Keldon", "Sorev Keldon", "Pale Willow Court"], ["Temperature 37 C"]),
    ("en", "Patient Luvira Menon entered from Silver Fern Arcade; contact person: Vasha Menon. Continue iron 30 mg daily.", ["Luvira Menon", "Vasha Menon", "Silver Fern Arcade"], ["iron 30 mg"]),
    ("en", "Clinical update for patient: Rorik Vell; spouse: Orena Vell; home address: Dusk Garden Row. BP 118/76.", ["Rorik Vell", "Orena Vell", "Dusk Garden Row"], ["BP 118/76"]),
    ("hi", "रोगी: तृणिका वेलोन\nपिता: शिरोमणि देव\nपता: नीलकमल मार्ग। बीपी 118/76; मेटफॉर्मिन 500 mg.", ["तृणिका वेलोन", "शिरोमणि देव", "नीलकमल मार्ग"], ["बीपी 118/76", "मेटफॉर्मिन 500 mg"]),
    ("hi", "मरीज देविका सैरिन जांच हेतु आईं; पिता शौर्यन वेल साथ थे। घर का पता: केसर आंगन। नाड़ी 72 bpm.", ["देविका सैरिन", "शौर्यन वेल", "केसर आंगन"], ["नाड़ी 72 bpm"]),
    ("hi", "नाम: इरावती मेहेर; पति: अमरोज मेहेर; निवास: चंद्र वन पथ। ग्लूकोज़ 94 mg/dL; दवा 5 mg.", ["इरावती मेहेर", "अमरोज मेहेर", "चंद्र वन पथ"], ["ग्लूकोज़ 94 mg/dL", "दवा 5 mg"]),
    ("hi", "रोगी नाम: संजना विहार; अभिभावक: ललन विहार; पता: केवड़ा चौक। बीपी 118/76; मेटफॉर्मिन 500 mg.", ["संजना विहार", "ललन विहार", "केवड़ा चौक"], ["बीपी 118/76", "मेटफॉर्मिन 500 mg"]),
    ("hi", "प्रवेश पर मरीज: पल्लवी रौन; रिश्तेदार: नीलम रौन; पता: गुलमोहर आंगन। तापमान 37 C.", ["पल्लवी रौन", "नीलम रौन", "गुलमोहर आंगन"], ["तापमान 37 C"]),
    ("hi", "मरीज मृणाल वेद को देखा। पति अच्युत वेद साथ थे। निवास स्थल: पीपल वन। नाड़ी 72 bpm.", ["मृणाल वेद", "अच्युत वेद", "पीपल वन"], ["नाड़ी 72 bpm"]),
    ("hi", "पंजीकरण: अवनि तोमर; पिता का नाम: रचित तोमर; घर: मोर पंख गली। रक्तचाप 120/80; दवा 10 mg.", ["अवनि तोमर", "रचित तोमर", "मोर पंख गली"], ["रक्तचाप 120/80", "दवा 10 mg"]),
    ("hi", "रोगी: काव्या नीर; पुत्री: ईशा नीर; पता: अमलतास पथ। बीपी 118/76; मेटफॉर्मिन 500 mg.", ["काव्या नीर", "ईशा नीर", "अमलतास पथ"], ["बीपी 118/76", "मेटफॉर्मिन 500 mg"]),
    ("hinglish", "Patient Kavira Norrin aaj OPD mein aayi; father: Soren Luvak; Pata: Gulmohar Gali. BP 118/76; Metformin 500 mg.", ["Kavira Norrin", "Soren Luvak", "Gulmohar Gali"], ["BP 118/76", "Metformin 500 mg"]),
    ("hinglish", "Naam: Juvira Senol; guardian: Taren Senol; address: Violet Ridge Lane. Sugar 94 mg/dL; tablet 5 mg.", ["Juvira Senol", "Taren Senol", "Violet Ridge Lane"], ["Sugar 94 mg/dL", "tablet 5 mg"]),
    ("hinglish", "The patient Narel Voss came with his wife Evara Voss; ghar: Kesar Bagh Road. BP 120/80.", ["Narel Voss", "Evara Voss", "Kesar Bagh Road"], ["BP 120/80"]),
    ("hinglish", "Patient: Harin Dovek; W/o: Rilana Dovek; Pata: Peacock Street. Pulse 72 bpm; aspirin 75 mg.", ["Harin Dovek", "Rilana Dovek", "Peacock Street"], ["Pulse 72 bpm", "aspirin 75 mg"]),
    ("hinglish", "Aaj patient Liora Seneth ko dekha; unke papa Miran Seneth saath aaye; home is Amber Orchard Path. BP 118/76.", ["Liora Seneth", "Miran Seneth", "Amber Orchard Path"], ["BP 118/76"]),
    ("hinglish", "Patient name: Nirel Vana; relative name: Tovira Vana; address: Banyan Court. Glucose 94 mg/dL.", ["Nirel Vana", "Tovira Vana", "Banyan Court"], ["Glucose 94 mg/dL"]),
    ("hinglish", "OPD note: patient Ravan Elmir, accompanied by sister Silev Elmir. Pata: Morning Dew Colony. BP 120/80.", ["Ravan Elmir", "Silev Elmir", "Morning Dew Colony"], ["BP 120/80"]),
    ("hinglish", "Review for patient: Kelven Toran; father: Doren Toran; residence: Marigold Bend. Metformin 500 mg; BP 118/76.", ["Kelven Toran", "Doren Toran", "Marigold Bend"], ["Metformin 500 mg", "BP 118/76"]),
]


def contains(text: str, value: str) -> bool:
    return value.casefold() in text.casefold()


def run_pipeline_sample(text: str, model: CandidateModels | None) -> str:
    output: dict[str, bytes] = {}
    report, _ = run_pipeline([("case.txt", text.encode("utf-8"))], output, "synthetic-ablation-secret", model)
    declared = next(item for item in report["files"] if item["output"])
    return output[declared["output"]].decode("utf-8")


def crf_only(text: str, model: CandidateModels) -> tuple[str, list[dict]]:
    spans = [span for span in model.spans(text) if span["label"] != "CLINICAL"]
    result = text
    for span in sorted(spans, key=lambda item: item["start"], reverse=True):
        result = result[: span["start"]] + "[CRF_REDACTED]" + result[span["end"] :]
    return result, spans


def score() -> dict:
    model = CandidateModels()
    totals = defaultdict(lambda: {"pii_total": 0, "pii_removed": 0, "clinical_total": 0, "clinical_kept": 0})
    crf_span_total = crf_span_hits = crf_gold_total = crf_gold_hits = 0
    labels = defaultdict(int)

    for lang, text, pii, clinical in SAMPLES:
        crf_output, crf_spans = crf_only(text, model)
        outputs = {
            "rules_only": run_pipeline_sample(text, None),
            "standalone_crf": crf_output,
            "hybrid": run_pipeline_sample(text, model),
        }
        gold_ranges = [(text.casefold().find(value.casefold()), text.casefold().find(value.casefold()) + len(value)) for value in pii]
        if any(start < 0 for start, _ in gold_ranges):
            raise ValueError("A gold PII surface is absent from its sample")
        crf_gold_total += len(gold_ranges)
        crf_gold_hits += sum(any(span["start"] < end and span["end"] > start for span in crf_spans) for start, end in gold_ranges)
        crf_span_total += len(crf_spans)
        crf_span_hits += sum(any(span["start"] < end and span["end"] > start for start, end in gold_ranges) for span in crf_spans)
        for span in crf_spans:
            labels[span["label"]] += 1

        for mode, output in outputs.items():
            row = totals[(mode, lang)]
            row["pii_total"] += len(pii)
            row["pii_removed"] += sum(not contains(output, value) for value in pii)
            row["clinical_total"] += len(clinical)
            row["clinical_kept"] += sum(contains(output, value) for value in clinical)

    return {
        "scope": "24 hand-authored, fictional samples (8 English, 8 Hindi, 8 Hinglish); no organizer practice/training records used; each sample processed independently",
        "method": "Rules and hybrid use the normal run_pipeline with a single sample. Standalone CRF directly redacts every non-CLINICAL model span, without rule/context validation. PII removal is exact gold-surface absence; clinical preservation is exact probe presence. CRF span precision/recall use any character overlap with a gold PII surface.",
        "sample_count": len(SAMPLES),
        "model_labels_directly_redacted": sorted(labels),
        "standalone_crf_span_precision": crf_span_hits / crf_span_total if crf_span_total else None,
        "standalone_crf_span_recall": crf_gold_hits / crf_gold_total if crf_gold_total else None,
        "standalone_crf_span_counts": {"true_positive": crf_span_hits, "predicted": crf_span_total, "gold": crf_gold_total},
        "by_mode_and_language": {
            f"{mode}_{lang}": {
                **counts,
                "pii_surface_recall": counts["pii_removed"] / counts["pii_total"],
                "clinical_probe_preservation": counts["clinical_kept"] / counts["clinical_total"],
            }
            for (mode, lang), counts in sorted(totals.items())
        },
        "overall": {
            mode: {
                "pii_total": sum(counts["pii_total"] for (candidate, _), counts in totals.items() if candidate == mode),
                "pii_removed": sum(counts["pii_removed"] for (candidate, _), counts in totals.items() if candidate == mode),
                "clinical_total": sum(counts["clinical_total"] for (candidate, _), counts in totals.items() if candidate == mode),
                "clinical_kept": sum(counts["clinical_kept"] for (candidate, _), counts in totals.items() if candidate == mode),
                "pii_surface_recall": sum(counts["pii_removed"] for (candidate, _), counts in totals.items() if candidate == mode) / sum(counts["pii_total"] for (candidate, _), counts in totals.items() if candidate == mode),
                "clinical_probe_preservation": sum(counts["clinical_kept"] for (candidate, _), counts in totals.items() if candidate == mode) / sum(counts["clinical_total"] for (candidate, _), counts in totals.items() if candidate == mode),
            }
            for mode in ("rules_only", "standalone_crf", "hybrid")
        },
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(score(), ensure_ascii=False, indent=2))
