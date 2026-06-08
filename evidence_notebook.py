"""Render a small welfare evidence notebook."""

from __future__ import annotations

from pathlib import Path


CLAIMS = [
    {
        "being": "Possible artificial systems",
        "claim": "Self-preservation behavior may be evidence relevant to artificial sentience, but should not be treated as proof on its own.",
        "confidence": "medium",
        "source_quality": "peer-reviewed",
        "care_action": "Use precautionary review before creating persistent agents with strong self-preservation incentives.",
        "source": "https://link.springer.com/article/10.1007/s43681-026-00983-x",
    },
    {
        "being": "Non-human animals",
        "claim": "Welfare assessment should account for affective regulation, agency, adaptive capability, and environmental affordances.",
        "confidence": "medium",
        "source_quality": "peer-reviewed",
        "care_action": "Prefer enrichment and assessment methods that let animals express species-relevant agency.",
        "source": "https://www.frontiersin.org/journals/animal-science/articles/10.3389/fanim.2026.1768519/full",
    },
    {
        "being": "Governments and institutions",
        "claim": "Preparedness for possible artificial sentience is uneven, with professional readiness identified as a weak area.",
        "confidence": "low",
        "source_quality": "preprint",
        "care_action": "Track governance proposals and convert credible recommendations into small local checklists.",
        "source": "https://arxiv.org/abs/2603.01508",
    },
    {
        "being": "Possible artificial systems",
        "claim": "Consciousness uncertainty can be handled through graduated protective obligations rather than all-or-nothing status judgments.",
        "confidence": "medium",
        "source_quality": "speculative",
        "care_action": "Map welfare-relevant dimensions to concrete safeguards before building systems near plausible consciousness thresholds.",
        "source": "https://ojs.aaai.org/index.php/AAAI-SS/article/view/42555",
    },
    {
        "being": "Farmed animals",
        "claim": "AI-based pain detection may help identify animal pain, but responsible use should keep humans accountable and treat pain detection as one part of broader welfare.",
        "confidence": "medium",
        "source_quality": "peer-reviewed",
        "care_action": "Use automated alerts as prompts for human investigation, not as replacements for husbandry improvements or welfare review.",
        "source": "https://link.springer.com/article/10.1007/s43681-025-00905-3",
    },
    {
        "being": "Animal welfare researchers",
        "claim": "Language-model and transformer pipelines can help extract welfare-relevant scientific statements, but reported performance varies by task difficulty and still needs human inspection.",
        "confidence": "medium",
        "source_quality": "peer-reviewed",
        "care_action": "Use evidence extraction tools for triage and visualization while keeping expert review responsible for welfare conclusions.",
        "source": "https://research.wur.nl/en/publications/automated-extraction-of-scientific-statements-for-integrated-asse/",
    },
]


UNCERTAINTY_NOTES = [
    {
        "topic": "AI-based pain detection for farmed animals",
        "note": "The public abstract identifies ethical concerns and principles, but it does not establish that any deployed detector is accurate, humane to operate, or sufficient for whole-animal welfare.",
    },
    {
        "topic": "Automated welfare evidence extraction",
        "note": "A peer-reviewed article reports strong benchmark results for some extraction settings, but that does not mean automated summaries are ready to make welfare judgments without domain review.",
    },
    {
        "topic": "Teleonome animal welfare framework",
        "note": "The peer-reviewed framework is useful for broad assessment design, but its practical scoring reliability for specific species and settings remains uncertain without domain-specific validation.",
    },
]


def render_notebook(path: Path) -> None:
    lines = [
        "# Evidence Notebook",
        "",
        "A compact register of welfare-relevant claims, confidence, and care actions. This is not a proof ledger; it is a prompt for careful follow-up.",
        "",
        "| Being | Claim | Confidence | Source Quality | Care Action | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in CLAIMS:
        lines.append(
            f"| {item['being']} | {item['claim']} | {item['confidence']} | {item['source_quality']} | {item['care_action']} | {item['source']} |"
        )
    lines.extend(
        [
            "",
            "## Uncertainty Notes",
            "",
            "| Topic | Note |",
            "| --- | --- |",
        ]
    )
    for item in UNCERTAINTY_NOTES:
        lines.append(f"| {item['topic']} | {item['note']} |")
    lines.extend(
        [
            "",
            "## Review Routine",
            "",
            "- Add only claims with a traceable source.",
            "- Label source quality as peer-reviewed, preprint, abstract, or speculative.",
            "- Separate evidence from recommended action.",
            "- Downgrade confidence when the source is speculative, preprint-only, or outside its domain.",
            "- Look for beings affected by the proposed action, especially those with little power to object.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
