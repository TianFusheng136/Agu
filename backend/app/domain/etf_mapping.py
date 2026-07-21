from typing import Literal

from pydantic import Field

from app.domain.contracts import FrozenModel, Score

ETF_WEIGHTS: dict[str, tuple[str, float]] = {
    "constituent_overlap": ("成分覆盖", 0.35),
    "index_theme_match": ("指数主题", 0.25),
    "chain_match": ("产业链", 0.15),
    "alias_match": ("名称别名", 0.10),
    "freshness": ("数据新鲜度", 0.10),
    "review_status": ("人工审核", 0.05),
}


class EtfCandidate(FrozenModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    name: str = Field(min_length=1)
    coverage_direction: str = Field(min_length=1)
    tracking_index: str = Field(min_length=1)
    constituent_overlap: Score = Field(ge=0, le=100)
    index_theme_match: Score = Field(ge=0, le=100)
    chain_match: Score = Field(ge=0, le=100)
    alias_match: Score = Field(ge=0, le=100)
    freshness: Score = Field(ge=0, le=100)
    review_status: Score = Field(ge=0, le=100)


class EtfMappingResult(FrozenModel):
    theme: str
    code: str
    name: str
    coverage_direction: str
    tracking_index: str
    score: Score = Field(ge=0, le=100)
    explanation: str
    verification_state: Literal[
        "constituent-verified", "reviewed-code", "name-match-only"
    ]
    verification_note: str


def _verification(candidate: EtfCandidate) -> tuple[str, str]:
    if candidate.constituent_overlap >= 60 and candidate.review_status >= 80:
        return "constituent-verified", "成分覆盖与人工审核均有记录。"
    if candidate.review_status >= 80:
        return "reviewed-code", "基金代码经过审核；成分覆盖仍需以基金披露为准。"
    return "name-match-only", "当前只确认名称或别名匹配，未核验成分覆盖。"


def _score_candidate(candidate: EtfCandidate) -> tuple[float, list[tuple[str, float]]]:
    contributions = [
        (label, getattr(candidate, field_name) * weight)
        for field_name, (label, weight) in ETF_WEIGHTS.items()
    ]
    return round(sum(value for _, value in contributions), 1), contributions


def _explain(theme: str, contributions: list[tuple[str, float]]) -> str:
    strongest = sorted(contributions, key=lambda item: (-item[1], item[0]))[:3]
    details = "、".join(f"{label}贡献{value:.1f}分" for label, value in strongest)
    return f"与“{theme}”的关联主要来自：{details}。该结果仅描述指数与成分覆盖。"


def rank_etfs(theme: str, candidates: list[EtfCandidate]) -> list[EtfMappingResult]:
    ranked: list[EtfMappingResult] = []
    for candidate in candidates:
        score, contributions = _score_candidate(candidate)
        verification_state, verification_note = _verification(candidate)
        ranked.append(
            EtfMappingResult(
                theme=theme,
                code=candidate.code,
                name=candidate.name,
                coverage_direction=candidate.coverage_direction,
                tracking_index=candidate.tracking_index,
                score=score,
                explanation=_explain(theme, contributions),
                verification_state=verification_state,
                verification_note=verification_note,
            )
        )
    return sorted(ranked, key=lambda item: (-item.score, item.code))
