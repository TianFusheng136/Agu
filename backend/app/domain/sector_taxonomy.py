import re
from typing import Literal

from app.domain.contracts import FrozenModel

TAXONOMY_VERSION = "cn-industry-v1"
GENERIC_SECTOR_NAMES = frozenset({"综合", "其他"})

# Only deterministic, audited aliases are normalized. Unknown names remain as
# supplied by the upstream source instead of being guessed into a broad theme.
SECTOR_ALIASES = {
    "公路桥梁": "公路铁路运输",
    "铁路公路": "公路铁路运输",
    "公路铁路运输": "公路铁路运输",
    "煤炭": "煤炭开采加工",
    "煤炭开采加工": "煤炭开采加工",
    "石油": "油气开采及服务",
    "油气开采及服务": "油气开采及服务",
}


class SectorClassification(FrozenModel):
    canonical_name: str
    taxonomy_version: str = TAXONOMY_VERSION
    source_name: str
    status: Literal["source-native", "cross-source-mapped"]
    note: str


def is_generic_sector(name: str) -> bool:
    return name.strip() in GENERIC_SECTOR_NAMES


def canonical_sector_name(name: str) -> str:
    normalized = name.strip()
    return SECTOR_ALIASES.get(normalized, normalized)


def industry_sector_id(name: str) -> str:
    canonical_name = canonical_sector_name(name)
    return "industry-" + re.sub(r"\W+", "-", canonical_name.casefold()).strip("-")


def classify_sector(
    name: str,
    *,
    has_cross_source_mapping: bool,
) -> SectorClassification:
    source_name = "同花顺行业资金流"
    status: Literal["source-native", "cross-source-mapped"] = "source-native"
    note = "板块名称取自公开行业资金流分类。"
    if has_cross_source_mapping:
        source_name = "同花顺行业资金流 + 新浪行业行情"
        status = "cross-source-mapped"
        note = "名称以同花顺行业资金流为主，并与新浪行业行情交叉匹配。"

    return SectorClassification(
        canonical_name=canonical_sector_name(name),
        source_name=source_name,
        status=status,
        note=note,
    )
