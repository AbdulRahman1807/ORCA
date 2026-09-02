import os
import yaml

TERMS_DIR = os.path.join(os.path.dirname(__file__), "terms")
os.makedirs(TERMS_DIR, exist_ok=True)

base = {
    "domain": {
        "SAFETY": "Safety",
        "FISHING_SUITABILITY": "Fishing Suitability",
        "REGULATORY": "Regulatory"
    },
    "verdict": {
        "FAVOURABLE": "Favourable",
        "MARGINAL": "Marginal",
        "UNSAFE": "Unsafe",
        "PERMITTED": "Permitted",
        "RESTRICTED": "Restricted",
        "PROHIBITED": "Prohibited",
        "UNKNOWN": "Unknown",
        "INSUFFICIENT_EVIDENCE": "Insufficient Evidence"
    },
    "confidence": {
        "LOW": "low",
        "MEDIUM": "medium",
        "HIGH": "high"
    },
    "value": {
        "inside": "inside",
        "outside": "outside"
    },
    "phrase": {
        "assessment_base": "{domain}: {verdict} (confidence {confidence})",
        "limiting_factor": "; limiting factor {factor} at {val}",
        "missing_required": "; no verdict issued for want of {missing}",
        "verdict_capped_by": "; capped at this level because {capped} could not be checked",
        "not_checked": "  Not checked: {not_checked}.",
        "disclaimer": "This is an ORCA assessment, not an official advisory. Follow IMD and INCOIS bulletins."
    },
    "factor": {
        "significant_wave_height": "significant wave height",
        "wind_speed": "wind speed",
        "chlorophyll_ratio": "chlorophyll ratio",
        "official_warning_status": "official warning status",
        "EEZ": "EEZ",
        "territorial_sea": "territorial sea",
        "maritime_boundary": "maritime boundary"
    },
    "reason": {
        "INSUFFICIENT_COVERAGE": "Insufficient Coverage",
        "STALE_DATA": "Stale Data",
        "DATASET_UNAVAILABLE": "Dataset Unavailable",
        "AUTH_REQUIRED": "Auth Required",
        "NOT_RETRIEVED": "Not Retrieved"
    }
}

# English
with open(os.path.join(TERMS_DIR, "en.yaml"), "w") as f:
    yaml.dump(base, f, allow_unicode=True)

# Malayalam
ml = base.copy()
ml["domain"] = {"SAFETY": "സുരക്ഷ", "FISHING_SUITABILITY": "മത്സ്യബന്ധന അനുയോജ്യത", "REGULATORY": "നിയന്ത്രണം"}
ml["verdict"] = {"FAVOURABLE": "അനുകൂലം", "MARGINAL": "ശരാശരി", "UNSAFE": "അപകടകരം", "PERMITTED": "അനുവദനീയം", "RESTRICTED": "നിയന്ത്രിതം", "PROHIBITED": "നിരോധിച്ചിരിക്കുന്നു", "UNKNOWN": "അജ്ഞാതം", "INSUFFICIENT_EVIDENCE": "അപര്യാപ്തമായ തെളിവ്"}
with open(os.path.join(TERMS_DIR, "ml.yaml"), "w") as f:
    yaml.dump(ml, f, allow_unicode=True)

# Hindi
hi = base.copy()
hi["domain"] = {"SAFETY": "सुरक्षा", "FISHING_SUITABILITY": "मछली पकड़ने की उपयुक्तता", "REGULATORY": "नियामक"}
hi["verdict"] = {"FAVOURABLE": "अनुकूल", "MARGINAL": "सीमांत", "UNSAFE": "असुरक्षित", "PERMITTED": "अनुमत", "RESTRICTED": "प्रतिबंधित", "PROHIBITED": "निषिद्ध", "UNKNOWN": "अज्ञात", "INSUFFICIENT_EVIDENCE": "अपर्याप्त साक्ष्य"}
with open(os.path.join(TERMS_DIR, "hi.yaml"), "w") as f:
    yaml.dump(hi, f, allow_unicode=True)

# Tamil
ta = base.copy()
ta["domain"] = {"SAFETY": "பாதுகாப்பு", "FISHING_SUITABILITY": "மீன்பிடித்தல் பொருத்தம்", "REGULATORY": "ஒழுங்குமுறை"}
with open(os.path.join(TERMS_DIR, "ta.yaml"), "w") as f:
    yaml.dump(ta, f, allow_unicode=True)

# Telugu
te = base.copy()
te["domain"] = {"SAFETY": "భద్రత", "FISHING_SUITABILITY": "ఫిషింగ్ అనుకూలత", "REGULATORY": "నియంత్రణ"}
with open(os.path.join(TERMS_DIR, "te.yaml"), "w") as f:
    yaml.dump(te, f, allow_unicode=True)

# Bengali
bn = base.copy()
bn["domain"] = {"SAFETY": "নিরাপত্তা", "FISHING_SUITABILITY": "মাছ ধরার উপযুক্ততা", "REGULATORY": "নিয়ন্ত্রক"}
with open(os.path.join(TERMS_DIR, "bn.yaml"), "w") as f:
    yaml.dump(bn, f, allow_unicode=True)

# Generate placeholders for the rest
for lang in ["mr", "gu", "kn", "or", "pa", "ur"]:
    with open(os.path.join(TERMS_DIR, f"{lang}.yaml"), "w") as f:
        yaml.dump(base.copy(), f, allow_unicode=True)

print("Generated term YAML files.")
