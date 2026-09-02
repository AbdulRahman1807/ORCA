"""Cross-domain synthesis.

Domains are combined only in LANGUAGE, never in arithmetic
(12_RISK_AND_RECOMMENDATION_SPEC.md section 8).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..schemas.assessment import Assessment
from ..schemas.enums import (
    Confidence, Disposition, Domain, RegulatoryStatus, Verdict,
)

#: Which outcome most constrains action, most constraining first.
_PRIORITY: list[tuple[Domain, object]] = [
    (Domain.REGULATORY, RegulatoryStatus.PROHIBITED),
    (Domain.SAFETY, Verdict.UNSAFE),
    (Domain.SAFETY, Verdict.UNFAVOURABLE),
    (Domain.SAFETY, Verdict.MARGINAL),
    (Domain.REGULATORY, RegulatoryStatus.RESTRICTED),
    (Domain.FISHING_SUITABILITY, Verdict.UNFAVOURABLE),
    (Domain.FISHING_SUITABILITY, Verdict.MARGINAL),
]

_CATEGORY = {
    RegulatoryStatus.PROHIBITED: "DO_NOT_PROCEED",
    Verdict.UNSAFE: "DO_NOT_PROCEED",
    Verdict.UNFAVOURABLE: "ADVISE_AGAINST",
    Verdict.MARGINAL: "PROCEED_WITH_CAUTION",
}


@dataclass(slots=True)
class Synthesis:
    category: str
    headline: str
    limiting_domain: Domain | None
    limiting_factor: str | None
    confidence: Confidence
    disposition: Disposition


def synthesise(assessments: list[Assessment]) -> Synthesis:
    by_domain = {a.domain: a for a in assessments}
    safety = by_domain.get(Domain.SAFETY)

    # A safety question with no safety verdict is answered by refusing, not by
    # reporting the other domains as if they were the answer.
    if safety is not None and safety.verdict is Verdict.INSUFFICIENT_EVIDENCE:
        missing = ", ".join(safety.missing_required
                            or sorted({n.factor for n in safety.not_evaluated})[:3])
        return Synthesis(
            category="CANNOT_ADVISE",
            headline=("I cannot assess safety for this time and place, so I will not "
                      f"say whether it is safe to go. Missing: {missing}."),
            limiting_domain=Domain.SAFETY, limiting_factor=None,
            confidence=Confidence.LOW, disposition=Disposition.BLOCKED)

    if (safety is not None and safety.official_warning_status
            and safety.official_warning_status.get("active")):
        return Synthesis(
            category="DEFER_TO_OFFICIAL",
            headline=("An official marine warning is in force for this area. Follow it. "
                      "ORCA's role here is to convey and contextualise it."),
            limiting_domain=Domain.SAFETY,
            limiting_factor="official_warning_status",
            confidence=safety.confidence, disposition=Disposition.REVIEW_REQUIRED)

    for domain, verdict in _PRIORITY:
        a = by_domain.get(domain)
        if a is None or a.verdict is not verdict:
            continue
        others = [o for o in assessments
                  if o.domain is not domain
                  and o.verdict in (Verdict.FAVOURABLE, RegulatoryStatus.PERMITTED)]
        contrast = ""
        if others and domain is Domain.SAFETY:
            names = " and ".join(o.domain.value.replace("_", " ").lower()
                                 for o in others)
            contrast = (f" Conditions for {names} look favourable — the limiting "
                        f"factor is {a.limiting_factor}, not fish availability.")
        headline = {
            "DO_NOT_PROCEED": "Do not go. ",
            "ADVISE_AGAINST": "Going out is not advisable. ",
            "PROCEED_WITH_CAUTION": "Conditions are marginal. ",
        }.get(_CATEGORY.get(verdict, "PROCEED_WITH_CONTEXT"), "")
        headline += (f"{domain.value.replace('_', ' ').title()} is "
                     f"{str(getattr(verdict, 'value', verdict)).lower()}"
                     + (f" ({a.limiting_factor})." if a.limiting_factor else "."))
        return Synthesis(
            category=_CATEGORY.get(verdict, "PROCEED_WITH_CONTEXT"),
            headline=headline + contrast,
            limiting_domain=domain, limiting_factor=a.limiting_factor,
            confidence=a.confidence,
            disposition=(Disposition.REVIEW_REQUIRED
                         if verdict in (Verdict.UNSAFE, RegulatoryStatus.PROHIBITED)
                         else Disposition.AUTO_RELEASE))

    issued = [a for a in assessments if a.verdict is not Verdict.INSUFFICIENT_EVIDENCE]
    if not issued:
        return Synthesis("CANNOT_ADVISE",
                         "There is not enough evidence to assess any domain for this "
                         "time and place.", None, None, Confidence.LOW,
                         Disposition.BLOCKED)
    worst_conf = min((a.confidence for a in issued),
                     key=[Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH].index)
    return Synthesis("PROCEED_WITH_CONTEXT",
                     "No adverse conditions were identified in the domains that could "
                     "be assessed.", None, None, worst_conf, Disposition.AUTO_RELEASE)
