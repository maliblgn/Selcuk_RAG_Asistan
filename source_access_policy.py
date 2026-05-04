def build_access_policy_decision(
    manifest_item,
    include_inactive=False,
    authorized_source_mode=False,
    robots_override=False,
    robots_allowed=None,
    url="",
):
    """Manifest kaynagi icin dry-run erisim karari uret."""
    active = bool(manifest_item.get("active", True))
    requires_permission = bool(manifest_item.get("requires_permission", False))
    authorized_source_mode = bool(authorized_source_mode)
    robots_override = bool(robots_override)

    base = {
        "can_attempt_fetch": False,
        "blocked_by": "none",
        "requires_permission": requires_permission,
        "authorized_source_mode": authorized_source_mode,
        "robots_override": robots_override,
        "robots_allowed": robots_allowed,
        "message": "",
    }

    if not active and not include_inactive:
        base["blocked_by"] = "inactive"
        base["message"] = "Kaynak active=false ve --include-inactive verilmedi."
        return base

    if requires_permission and not authorized_source_mode:
        base["blocked_by"] = "requires_permission"
        base["message"] = "Kaynak requires_permission=true ve AUTHORIZED_SOURCE_MODE kapali."
        return base

    if robots_allowed is False and not (authorized_source_mode and robots_override):
        base["blocked_by"] = "robots"
        base["message"] = "robots.txt erisim izni vermiyor ve WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE kapali."
        return base

    base["can_attempt_fetch"] = True
    if robots_allowed is False and authorized_source_mode and robots_override:
        base["message"] = (
            "Yetkili mod aktif: AUTHORIZED_SOURCE_MODE ve "
            "WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE acik oldugu icin robots engeli "
            "bilincli/yetkili modda asiliyor."
        )
    else:
        base["message"] = "Kaynak erisim politikasi acisindan fetch denemesine uygun."

    return base
