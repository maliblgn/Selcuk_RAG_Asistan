import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from urllib.parse import unquote

from dotenv import load_dotenv

from web_crawler import CrawlerConfig, SelcukCrawler
from web_scraper import ScraperConfig, ScrapingError, URLValidator, WebScraper
from source_access_policy import build_access_policy_decision


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MANIFEST = os.path.join(BASE_DIR, "source_manifest.json")


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def active_seeds(manifest):
    authorized_mode = os.getenv("AUTHORIZED_SOURCE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    return [
        item for item in manifest.get("crawl_seeds", [])
        if (item.get("active", True) or (authorized_mode and item.get("requires_permission"))) and item.get("url")
    ]


def active_direct_sources(manifest):
    authorized_mode = os.getenv("AUTHORIZED_SOURCE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    return [
        item for item in manifest.get("known_direct_sources", [])
        if (item.get("active", True) or (authorized_mode and item.get("requires_permission"))) and item.get("url")
    ]


def normalize_text(value):
    value = unquote(value or "")
    return value.lower().replace("%20", " ")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def match_expected_documents(urls, expected_documents):
    normalized_urls = [(url, normalize_text(url)) for url in urls]
    matches = []
    for expected in expected_documents:
        keywords = [normalize_text(keyword) for keyword in expected.get("keywords", []) if keyword]
        matched_urls = []
        for original_url, normalized_url in normalized_urls:
            hit_count = sum(1 for keyword in keywords if keyword in normalized_url)
            if hit_count >= min(2, len(keywords)):
                matched_urls.append(original_url)
        matches.append({
            "id": expected.get("id"),
            "title": expected.get("title"),
            "priority": expected.get("priority"),
            "matched": bool(matched_urls),
            "matched_urls": matched_urls[:10],
        })
    return matches


def manifest_sources_by_id(manifest, source_ids, include_inactive=False):
    """Manifest icindeki kaynaklari id'ye gore bul."""
    wanted = set(source_ids or [])
    items = []
    for section in ("crawl_seeds", "known_direct_sources", "sources"):
        for item in manifest.get(section, []):
            if wanted and item.get("id") not in wanted:
                continue
            if not include_inactive and not item.get("active", True):
                continue
            if not item.get("url"):
                continue
            enriched = dict(item)
            enriched["_manifest_section"] = section
            items.append(enriched)
    return items


def fetch_pdf_inventory_for_source(source, scraper):
    """Tek liste sayfasindan PDF link envanteri cikar; PDF indirmez."""
    url = source.get("url", "")
    result = {
        "source_id": source.get("id"),
        "title": source.get("title"),
        "url": url,
        "active": bool(source.get("active", True)),
        "requires_permission": bool(source.get("requires_permission", False)),
        "fetch_ok": False,
        "error": None,
        "pdf_count": 0,
        "pdf_links": [],
        "access_policy": None,
    }

    normalized = URLValidator.normalize_url(url)
    if not URLValidator.is_valid_url(normalized):
        result["error"] = f"Gecersiz URL: {url}"
        return result

    if scraper.config.enable_domain_whitelist and not URLValidator.is_allowed_domain(
        normalized,
        scraper.config.allowed_domains,
    ):
        result["error"] = f"Whitelist disi domain: {normalized}"
        return result

    robots_allowed = URLValidator.is_allowed_by_robots_strict(normalized, scraper.config.user_agent)
    access_policy = build_access_policy_decision(
        source,
        include_inactive=True,
        authorized_source_mode=env_bool("AUTHORIZED_SOURCE_MODE", False),
        robots_override=env_bool("WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE", False),
        robots_allowed=robots_allowed,
        url=normalized,
    )
    result["access_policy"] = access_policy
    if not access_policy["can_attempt_fetch"]:
        result["error"] = access_policy["message"]
        return result

    try:
        response = scraper._request_with_retry(normalized, "Liste sayfasi cekilemedi")
    except ScrapingError as exc:
        result["error"] = str(exc)
        return result

    pdf_links = WebScraper.extract_pdf_link_inventory(response.text, normalized)
    result["fetch_ok"] = True
    result["pdf_links"] = pdf_links
    result["pdf_count"] = len(pdf_links)
    return result


def build_pdf_inventory_report(manifest_path, source_ids=None, include_inactive=False):
    manifest = load_manifest(manifest_path)
    sources = manifest_sources_by_id(
        manifest,
        source_ids=source_ids,
        include_inactive=include_inactive,
    )
    scraper = WebScraper(ScraperConfig.from_env())
    reports = [fetch_pdf_inventory_for_source(source, scraper) for source in sources]

    unique_pdfs = {
        pdf["normalized_url"]
        for source in reports
        for pdf in source.get("pdf_links", [])
        if pdf.get("normalized_url")
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "pdf_inventory_only",
        "manifest_path": manifest_path,
        "source_ids": source_ids or [],
        "include_inactive": include_inactive,
        "sources": reports,
        "totals": {
            "source_count": len(reports),
            "fetch_ok": sum(1 for source in reports if source.get("fetch_ok")),
            "fetch_failed": sum(1 for source in reports if not source.get("fetch_ok")),
            "pdf_count": sum(source.get("pdf_count", 0) for source in reports),
            "unique_pdf_count": len(unique_pdfs),
        },
    }


def build_access_preflight_report(manifest_path, source_ids=None, include_inactive=False):
    manifest = load_manifest(manifest_path)
    sources = manifest_sources_by_id(
        manifest,
        source_ids=source_ids,
        include_inactive=include_inactive,
    )
    scraper_config = ScraperConfig.from_env()
    authorized_source_mode = env_bool("AUTHORIZED_SOURCE_MODE", False)
    robots_override = env_bool("WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE", False)
    reports = []

    for source in sources:
        url = source.get("url", "")
        normalized = URLValidator.normalize_url(url)
        robots_allowed = None
        error = None
        if not URLValidator.is_valid_url(normalized):
            error = f"Gecersiz URL: {url}"
        elif scraper_config.enable_domain_whitelist and not URLValidator.is_allowed_domain(
            normalized,
            scraper_config.allowed_domains,
        ):
            error = f"Whitelist disi domain: {normalized}"
        else:
            robots_allowed = URLValidator.is_allowed_by_robots_strict(
                normalized,
                scraper_config.user_agent,
            )

        access_policy = build_access_policy_decision(
            source,
            include_inactive=include_inactive,
            authorized_source_mode=authorized_source_mode,
            robots_override=robots_override,
            robots_allowed=robots_allowed,
            url=normalized,
        )
        if error:
            access_policy["can_attempt_fetch"] = False
            access_policy["blocked_by"] = "network" if "Whitelist" not in error and "Gecersiz" not in error else access_policy["blocked_by"]
            access_policy["message"] = error

        reports.append({
            "source_id": source.get("id"),
            "title": source.get("title"),
            "url": url,
            "active": bool(source.get("active", True)),
            "requires_permission": bool(source.get("requires_permission", False)),
            "access_policy": access_policy,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "access_preflight_only",
        "manifest_path": manifest_path,
        "source_ids": source_ids or [],
        "include_inactive": include_inactive,
        "sources": reports,
        "totals": {
            "source_count": len(reports),
            "can_attempt_fetch": sum(
                1 for source in reports
                if source.get("access_policy", {}).get("can_attempt_fetch")
            ),
            "blocked": sum(
                1 for source in reports
                if not source.get("access_policy", {}).get("can_attempt_fetch")
            ),
        },
    }


def write_access_policy_markdown(report, path, command):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# Faz 1B Erişim Politikası Raporu",
        "",
        f"Rapor tarihi: {report.get('generated_at')}",
        "",
        "## 1. Amaç",
        "",
        "Bu rapor kritik kaynaklar için robots.txt ve permission durumunu güvenli şekilde raporlar. Preflight modu sayfa HTML'i çekmez, PDF link çıkarmaz, PDF indirmez, ingestion çalıştırmaz ve ChromaDB'ye dokunmaz.",
        "",
        "## 2. Varsayılan Güvenli Mod",
        "",
        "`AUTHORIZED_SOURCE_MODE=false` iken `requires_permission=true` kaynaklar fetch denemesine alınmaz. `WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE=false` iken robots.txt engeli aşılmaz. Pasif kaynaklar sadece `--include-inactive` ile raporlama amacıyla değerlendirilir; manifestteki `active=false` değerleri değiştirilmez.",
        "",
        "## 3. Kritik Kaynakların Preflight Sonucu",
        "",
        "| source_id | active | requires_permission | authorized_source_mode | robots_override | robots_allowed | can_attempt_fetch | blocked_by | message |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]

    for source in report.get("sources", []):
        policy = source.get("access_policy", {})
        lines.append(
            "| {source_id} | {active} | {requires_permission} | {authorized} | {override} | {robots_allowed} | {can_fetch} | {blocked_by} | {message} |".format(
                source_id=source.get("source_id"),
                active=str(source.get("active")).lower(),
                requires_permission=str(source.get("requires_permission")).lower(),
                authorized=str(policy.get("authorized_source_mode")).lower(),
                override=str(policy.get("robots_override")).lower(),
                robots_allowed=str(policy.get("robots_allowed")).lower(),
                can_fetch=str(policy.get("can_attempt_fetch")).lower(),
                blocked_by=policy.get("blocked_by"),
                message=policy.get("message"),
            )
        )

    lines.extend([
        "",
        "## 4. İzinli Mod Notu",
        "",
        "Kritik kaynaklar için kurumsal/yazılı izin varsa izinli mod `.env` üzerinden bilinçli şekilde açılmalıdır: `AUTHORIZED_SOURCE_MODE=true`. robots engelini yetkili modda aşmak gerekiyorsa ayrıca `WEB_SCRAPER_AUTHORIZED_ROBOTS_OVERRIDE=true` gerekir. Bu iki ayar varsayılan olarak kapalı kalmalıdır ve açıkken raporlarda/loglarda görünür olmalıdır.",
        "",
        "## 5. Sonraki Teknik Adım",
        "",
        "Kaynaklar izinli modda erişilebilir hale getirilirse önce PDF inventory dry-run tekrar çalıştırılmalı, ardından ayrı bir fazda PDF fetch dayanıklılığı ve ingestion öncesi kaynak seçimi ele alınmalıdır.",
        "",
        "## Çalıştırılan Komut",
        "",
        "```powershell",
        command,
        "```",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_pdf_inventory_markdown(report, path, command):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# Faz 1A Kritik PDF Envanter Raporu",
        "",
        f"Rapor tarihi: {report.get('generated_at')}",
        "",
        "## 1. Amaç",
        "",
        "Bu rapor PDF indirme, PDF parse etme, ChromaDB'ye yazma veya ingestion amacı taşımaz. Sadece manifestteki kritik liste sayfalarının HTML içeriğinden PDF link envanteri çıkarmak için üretilmiştir.",
        "",
        "## 2. Çalıştırılan Komut",
        "",
        "```powershell",
        command,
        "```",
        "",
        "## 3. Kaynak Bazlı Sonuçlar",
        "",
    ]

    for source in report.get("sources", []):
        lines.extend([
            f"### {source.get('source_id')}",
            "",
            f"- Başlık: {source.get('title')}",
            f"- URL: `{source.get('url')}`",
            f"- Active: `{str(source.get('active')).lower()}`",
            f"- Requires permission: `{str(source.get('requires_permission')).lower()}`",
            f"- Fetch sonucu: {'Başarılı' if source.get('fetch_ok') else 'Başarısız'}",
            f"- Hata: {source.get('error') or 'Yok'}",
            f"- Bulunan PDF sayısı: {source.get('pdf_count', 0)}",
            "",
        ])
        links = source.get("pdf_links", [])[:10]
        if links:
            lines.extend([
                "| # | PDF başlığı | URL |",
                "|---:|---|---|",
            ])
            for index, pdf in enumerate(links, start=1):
                lines.append(f"| {index} | {pdf.get('title')} | `{pdf.get('normalized_url')}` |")
            lines.append("")
        else:
            lines.extend(["İlk 10 PDF listesi: PDF linki bulunamadı.", ""])

    totals = report.get("totals", {})
    lines.extend([
        "## 4. Toplamlar",
        "",
        f"- Toplam kaynak: {totals.get('source_count', 0)}",
        f"- Başarıyla okunan liste sayfası: {totals.get('fetch_ok', 0)}",
        f"- Başarısız liste sayfası: {totals.get('fetch_failed', 0)}",
        f"- Toplam PDF linki: {totals.get('pdf_count', 0)}",
        f"- Benzersiz PDF linki: {totals.get('unique_pdf_count', 0)}",
        "",
        "## 5. Risk ve Gözlemler",
        "",
    ])

    if totals.get("pdf_count", 0) == 0:
        lines.extend([
            "- PDF linki bulunamadıysa sayfa HTML yapısı beklenenden farklı olabilir.",
            "- Linkler JavaScript ile sonradan yükleniyor olabilir.",
            "- Liste sayfasında PDF linkleri doğrudan `<a href=\"...pdf\">` olarak bulunmuyor olabilir.",
            "- robots.txt, whitelist, SSL veya network engeli liste sayfasının okunmasını engellemiş olabilir.",
        ])
    else:
        lines.extend([
            "- PDF linkleri bulundu; bu fazda PDF dosyaları indirilmedi ve parse edilmedi.",
            "- Bir sonraki fazda PDF fetch dayanıklılığı, robots/izin politikası ve ingestion öncesi kaynak seçimi ele alınabilir.",
        ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def run_seed(seed, defaults, allowed_domains):
    fd, state_path = tempfile.mkstemp(prefix="selcuk_discovery_", suffix=".json")
    os.close(fd)
    try:
        config = CrawlerConfig.from_env()
        config.seed_url = seed["url"]
        config.max_depth = int(defaults.get("max_depth", 1))
        config.max_pages = int(defaults.get("max_pages", 30))
        config.crawl_delay = float(defaults.get("delay_sec", 0.5))
        config.state_file = state_path
        if allowed_domains:
            config.allowed_domains = tuple(allowed_domains)

        crawler = SelcukCrawler(config=config)
        result = crawler.crawl()
        return {
            "seed_id": seed.get("id"),
            "seed_title": seed.get("title"),
            "seed_url": seed.get("url"),
            "stats": {
                "pages_crawled": result.stats.pages_crawled,
                "documents_found": result.stats.documents_found,
                "total_discovered": result.stats.total_discovered,
                "skipped_seen": result.stats.skipped_seen,
                "skipped_excluded": result.stats.skipped_excluded,
                "skipped_robots": result.stats.skipped_robots,
                "skipped_binary": result.stats.skipped_binary,
                "errors": result.stats.errors,
                "duration_sec": result.stats.duration_sec,
            },
            "text_pages": result.text_pages,
            "document_links": result.document_links,
            "failed_urls": result.failed_urls,
        }
    finally:
        if os.path.exists(state_path):
            os.remove(state_path)


def build_discovery_report(manifest_path, max_depth=None, max_pages=None):
    manifest = load_manifest(manifest_path)
    defaults = dict(manifest.get("crawl_defaults", {}))
    if max_depth is not None:
        defaults["max_depth"] = max_depth
    if max_pages is not None:
        defaults["max_pages"] = max_pages

    allowed_domains = manifest.get("allowed_domains", [])
    seed_reports = [
        run_seed(seed, defaults, allowed_domains)
        for seed in active_seeds(manifest)
    ]

    all_text_pages = []
    all_document_links = []
    all_failed_urls = []
    for report in seed_reports:
        all_text_pages.extend(report["text_pages"])
        all_document_links.extend(report["document_links"])
        all_failed_urls.extend(report["failed_urls"])

    direct_urls = [item["url"] for item in active_direct_sources(manifest)]
    all_candidate_urls = sorted(set(all_document_links + direct_urls))
    expected_matches = match_expected_documents(
        all_candidate_urls,
        manifest.get("expected_documents", []),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest_path": manifest_path,
        "crawl_defaults": defaults,
        "seed_count": len(seed_reports),
        "totals": {
            "unique_text_pages": len(set(all_text_pages)),
            "unique_document_links": len(set(all_document_links)),
            "failed_urls": len(set(all_failed_urls)),
        },
        "seed_reports": seed_reports,
        "known_direct_sources": direct_urls,
        "expected_document_matches": expected_matches,
    }


def print_human(report):
    print("=== Selcuk Web Discovery Report ===")
    print(f"Seeds              : {report['seed_count']}")
    print(f"Unique text pages  : {report['totals']['unique_text_pages']}")
    print(f"Unique documents   : {report['totals']['unique_document_links']}")
    print(f"Failed URLs        : {report['totals']['failed_urls']}")
    print("\nPer seed:")
    for seed in report["seed_reports"]:
        stats = seed["stats"]
        print(
            f"  - {seed['seed_id']}: pages={stats['pages_crawled']} "
            f"docs={stats['documents_found']} links={stats['total_discovered']} "
            f"robots={stats.get('skipped_robots', 0)} errors={stats['errors']}"
        )
    print("\nExpected documents:")
    for item in report["expected_document_matches"]:
        status = "FOUND" if item["matched"] else "MISSING"
        print(f"  - {status}: {item['id']} - {item['title']}")
        for url in item["matched_urls"][:3]:
            print(f"      {url}")


def parse_args():
    parser = argparse.ArgumentParser(description="Resmi web kaynaklarindan dokuman kesif raporu uretir.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Kaynak manifesti JSON yolu")
    parser.add_argument("--max-depth", type=int, default=None, help="Manifest derinligini override eder")
    parser.add_argument("--max-pages", type=int, default=None, help="Manifest sayfa limitini override eder")
    parser.add_argument("--source-id", action="append", default=[], help="Sadece belirtilen manifest source id'sini isle")
    parser.add_argument("--pdf-inventory-only", action="store_true", help="Liste sayfalarindan sadece PDF link envanteri cikar")
    parser.add_argument("--access-preflight-only", action="store_true", help="Kaynak erisim politikasini HTML cekmeden raporla")
    parser.add_argument("--include-inactive", action="store_true", help="Pasif manifest kaynaklarini sadece raporlama amaciyla dahil et")
    parser.add_argument(
        "--markdown-out",
        default=None,
        help="PDF envanter modu icin Markdown rapor yolu",
    )
    parser.add_argument("--json", action="store_true", help="Raporu JSON olarak yazdir")
    parser.add_argument("--out", help="JSON raporu dosyaya yaz")
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    if args.access_preflight_only:
        report = build_access_preflight_report(
            args.manifest,
            source_ids=args.source_id,
            include_inactive=args.include_inactive,
        )
        command = (
            ".\\venv\\Scripts\\python.exe discovery_report.py "
            f"--manifest {args.manifest} "
            + " ".join(f"--source-id {source_id}" for source_id in args.source_id)
            + (" --include-inactive" if args.include_inactive else "")
            + " --access-preflight-only"
            + (" --json" if args.json else "")
            + (f" --out {args.out}" if args.out else "")
        )
        markdown_out = args.markdown_out or os.path.join(
            BASE_DIR,
            "docs",
            "FAZ1B_ERISIM_POLITIKASI_RAPORU.md",
        )
        write_access_policy_markdown(report, markdown_out, command.strip())
    elif args.pdf_inventory_only:
        report = build_pdf_inventory_report(
            args.manifest,
            source_ids=args.source_id,
            include_inactive=args.include_inactive,
        )
        command = (
            ".\\venv\\Scripts\\python.exe discovery_report.py "
            f"--manifest {args.manifest} "
            + " ".join(f"--source-id {source_id}" for source_id in args.source_id)
            + (" --pdf-inventory-only" if args.pdf_inventory_only else "")
            + (" --include-inactive" if args.include_inactive else "")
            + (" --json" if args.json else "")
            + (f" --out {args.out}" if args.out else "")
        )
        markdown_out = args.markdown_out or os.path.join(
            BASE_DIR,
            "docs",
            "FAZ1A_KRITIK_PDF_ENVANTER_RAPORU.md",
        )
        write_pdf_inventory_markdown(report, markdown_out, command.strip())
    else:
        report = build_discovery_report(args.manifest, args.max_depth, args.max_pages)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.access_preflight_only:
        totals = report.get("totals", {})
        print("=== Selcuk Access Preflight Report ===")
        print(f"Sources           : {totals.get('source_count', 0)}")
        print(f"Can attempt fetch : {totals.get('can_attempt_fetch', 0)}")
        print(f"Blocked           : {totals.get('blocked', 0)}")
    elif args.pdf_inventory_only:
        totals = report.get("totals", {})
        print("=== Selcuk PDF Inventory Report ===")
        print(f"Sources          : {totals.get('source_count', 0)}")
        print(f"Fetch OK         : {totals.get('fetch_ok', 0)}")
        print(f"Fetch failed     : {totals.get('fetch_failed', 0)}")
        print(f"PDF links        : {totals.get('pdf_count', 0)}")
        print(f"Unique PDF links : {totals.get('unique_pdf_count', 0)}")
    else:
        print_human(report)


if __name__ == "__main__":
    main()
