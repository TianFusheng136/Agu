from app.domain.etf_mapping import EtfCandidate, rank_etfs


def test_rank_etfs_uses_explainable_weighted_score() -> None:
    candidates = [
        EtfCandidate(
            code="515980",
            name="人工智能ETF",
            coverage_direction="偏AI应用与计算机",
            tracking_index="中证人工智能产业指数",
            constituent_overlap=90,
            index_theme_match=95,
            chain_match=85,
            alias_match=100,
            freshness=90,
            review_status=100,
        ),
        EtfCandidate(
            code="512480",
            name="半导体ETF",
            coverage_direction="偏芯片产业链",
            tracking_index="中证全指半导体产品与设备指数",
            constituent_overlap=65,
            index_theme_match=70,
            chain_match=90,
            alias_match=55,
            freshness=90,
            review_status=100,
        ),
    ]

    ranked = rank_etfs("人工智能", candidates)

    assert [item.code for item in ranked] == ["515980", "512480"]
    assert ranked[0].score == 92.0
    assert "成分覆盖" in ranked[0].explanation
    assert ranked[0].theme == "人工智能"
    assert ranked[0].verification_state == "constituent-verified"
    assert "成分覆盖" in ranked[0].verification_note


def test_rank_etfs_marks_name_matches_without_constituent_review() -> None:
    ranked = rank_etfs(
        "人工智能",
        [
            EtfCandidate(
                code="515980",
                name="人工智能ETF",
                coverage_direction="名称匹配",
                tracking_index="以基金披露为准",
                constituent_overlap=0,
                index_theme_match=75,
                chain_match=55,
                alias_match=80,
                freshness=100,
                review_status=40,
            )
        ],
    )

    assert ranked[0].verification_state == "name-match-only"
    assert "未核验" in ranked[0].verification_note


def test_rank_etfs_uses_code_as_stable_tie_breaker() -> None:
    common = {
        "coverage_direction": "同一覆盖方向",
        "tracking_index": "测试指数",
        "constituent_overlap": 80,
        "index_theme_match": 80,
        "chain_match": 80,
        "alias_match": 80,
        "freshness": 80,
        "review_status": 80,
    }

    ranked = rank_etfs(
        "测试主题",
        [
            EtfCandidate(code="510002", name="测试ETF乙", **common),
            EtfCandidate(code="510001", name="测试ETF甲", **common),
        ],
    )

    assert [item.code for item in ranked] == ["510001", "510002"]
