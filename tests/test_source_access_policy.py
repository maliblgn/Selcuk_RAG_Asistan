from source_access_policy import build_access_policy_decision


def test_inactive_source_blocks_without_include_inactive():
    decision = build_access_policy_decision(
        {"active": False, "requires_permission": False},
        include_inactive=False,
        authorized_source_mode=False,
        robots_override=False,
        robots_allowed=True,
    )
    assert decision["can_attempt_fetch"] is False
    assert decision["blocked_by"] == "inactive"


def test_permission_source_blocks_without_authorized_mode():
    decision = build_access_policy_decision(
        {"active": True, "requires_permission": True},
        include_inactive=True,
        authorized_source_mode=False,
        robots_override=False,
        robots_allowed=True,
    )
    assert decision["can_attempt_fetch"] is False
    assert decision["blocked_by"] == "requires_permission"


def test_robots_blocks_without_override():
    decision = build_access_policy_decision(
        {"active": True, "requires_permission": False},
        include_inactive=True,
        authorized_source_mode=False,
        robots_override=False,
        robots_allowed=False,
    )
    assert decision["can_attempt_fetch"] is False
    assert decision["blocked_by"] == "robots"


def test_robots_override_allows_only_in_authorized_mode():
    decision = build_access_policy_decision(
        {"active": True, "requires_permission": True},
        include_inactive=True,
        authorized_source_mode=True,
        robots_override=True,
        robots_allowed=False,
    )
    assert decision["can_attempt_fetch"] is True
    assert decision["blocked_by"] == "none"
    assert "Yetkili mod aktif" in decision["message"]
    assert "WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE" in decision["message"]


def test_allowed_robots_and_permission_state_allows_fetch():
    decision = build_access_policy_decision(
        {"active": True, "requires_permission": True},
        include_inactive=True,
        authorized_source_mode=True,
        robots_override=False,
        robots_allowed=True,
    )
    assert decision["can_attempt_fetch"] is True
    assert decision["blocked_by"] == "none"
