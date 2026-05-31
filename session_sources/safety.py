"""URL safety checks for session-only manual sources."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests


BLOCKED_HOSTS = {"localhost", "0.0.0.0"}
BLOCKED_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}


@dataclass(frozen=True)
class URLSafetyResult:
    ok: bool
    reason: str = ""
    final_url: str = ""


def _is_private_address(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip in BLOCKED_METADATA_IPS
    )


def _resolve_host_private(hostname: str) -> bool:
    if not hostname:
        return True
    if hostname.casefold() in BLOCKED_HOSTS:
        return True
    if _is_private_address(hostname):
        return True
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError:
        return False
    return any(_is_private_address(item[4][0]) for item in infos)


def validate_url_safety(url: str) -> URLSafetyResult:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return URLSafetyResult(False, "Sadece http/https linkleri desteklenir.")
    if not parsed.hostname:
        return URLSafetyResult(False, "URL içinde geçerli bir host bulunamadı.")
    if _resolve_host_private(parsed.hostname):
        return URLSafetyResult(False, "Güvenlik nedeniyle localhost/private/internal adresler engellenir.")
    return URLSafetyResult(True)


def validate_final_url(url: str) -> URLSafetyResult:
    result = validate_url_safety(url)
    if not result.ok:
        return result
    return URLSafetyResult(True, final_url=url)


def robots_allowed(url: str, user_agent: str = "*", timeout_sec: int = 5) -> URLSafetyResult:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = requests.get(robots_url, timeout=timeout_sec, headers={"User-Agent": "SelcukRAGSessionSource/1.0"})
    except Exception:
        return URLSafetyResult(True, "robots.txt okunamadı; erişim denemesi normal HTTP sonucuna bırakıldı.")
    if response.status_code >= 400:
        return URLSafetyResult(True, "robots.txt bulunamadı veya okunamadı.")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    if not parser.can_fetch(user_agent, url):
        return URLSafetyResult(False, "Bu site otomatik erişime robots.txt tarafından izin vermiyor.")
    return URLSafetyResult(True)
