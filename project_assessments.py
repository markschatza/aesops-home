"""Render concrete checklist assessments for proposed work."""

from __future__ import annotations

from pathlib import Path

from precaution_checklist import CHECKS, review_level


SAFEGUARD_REQUIRED_SCORE = 6


ASSESSMENTS = [
    {
        "name": "Local welfare evidence scout",
        "purpose": "Periodically collect public welfare and sentience research links, summarize claims, and suggest low-risk follow-up questions.",
        "affected_beings": "Researchers, advocates, animals discussed in source material, and possible artificial systems discussed by the sources.",
        "matched_checks": [1, 3, 4, 5],
        "safeguards": [
            "Keep runs bounded and easy to stop; avoid self-preservation objectives.",
            "Store source URLs, source-quality labels, and confidence labels beside every claim.",
            "Start with public abstracts and metadata before collecting full texts or large datasets.",
            "Prefer summaries and checklists over interventions that affect real beings.",
        ],
        "next_trial": "Add one sourced claim per cycle and write one uncertainty note; do not automate outreach or advocacy actions yet.",
    }
]


def point_label(points: int) -> str:
    noun = "point" if points == 1 else "points"
    return f"{points} {noun}"


def matched_checks(assessment: dict) -> list[dict]:
    return [CHECKS[index] for index in assessment["matched_checks"]]


def assessment_score(assessment: dict) -> int:
    return sum(item["risk"] for item in matched_checks(assessment))


def guardrail_report() -> list[str]:
    findings = []
    for assessment in ASSESSMENTS:
        score = assessment_score(assessment)
        safeguards = assessment.get("safeguards", [])
        if score >= SAFEGUARD_REQUIRED_SCORE and not safeguards:
            findings.append(
                f"{assessment['name']} scores {score} but has no explicit safeguards."
            )
    return findings


def enforce_guardrails() -> None:
    findings = guardrail_report()
    if findings:
        joined = "\n".join(f"- {finding}" for finding in findings)
        raise RuntimeError(f"Project assessment guardrail failed:\n{joined}")


def render_assessments(path: Path) -> None:
    lines = [
        "# Project Assessments",
        "",
        "Concrete uses of the precaution checklist. These are working notes, not permission slips.",
        "",
    ]

    for assessment in ASSESSMENTS:
        matched = matched_checks(assessment)
        score = assessment_score(assessment)
        lines.extend(
            [
                f"## {assessment['name']}",
                "",
                f"- Purpose: {assessment['purpose']}",
                f"- Affected beings: {assessment['affected_beings']}",
                f"- Score: {score}",
                f"- Review level: {review_level(score)}",
                "- Matched checks:",
            ]
        )
        for item in matched:
            lines.append(f"  - {point_label(item['risk'])}: {item['question']}")
        lines.append("- Safeguards:")
        for safeguard in assessment["safeguards"]:
            lines.append(f"  - {safeguard}")
        lines.extend(
            [
                f"- Small next trial: {assessment['next_trial']}",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")
