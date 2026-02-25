"""
Модуль поиска информации по домену.
Без Flet — возвращает текст и структурированные данные для использования в панели проекта.
Зависимости: только стандартная библиотека + dnspython, requests (уже в проекте).
"""
import re
import socket
import ssl
import subprocess
from typing import Any

try:
    import dns.resolver
except ImportError:
    dns = None

try:
    import requests
except ImportError:
    requests = None


def _normalize_domain(domain: str) -> str:
    """Приведение домена к виду example.com."""
    s = (domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    if "/" in s:
        s = s.split("/")[0]
    if s.startswith("www."):
        s = s[4:]
    return s


def _validate_domain(domain: str) -> tuple[bool, str | None]:
    """Валидация домена. Возвращает (ok, error_message)."""
    if not domain or not domain.strip():
        return False, "Домен не может быть пустым"
    domain = _normalize_domain(domain)
    if " " in domain:
        return False, "Неверный формат домена"
    if "." not in domain:
        return False, "Неверный формат домена"
    if not re.match(r"^[a-z0-9][a-z0-9.-]*\.[a-z0-9.-]+$", domain):
        return False, "Неверный формат домена"
    return True, None


def _get_ip(domain: str) -> str | None:
    """Получение IP адреса домена через DNS или socket."""
    try:
        if dns:
            answers = dns.resolver.resolve(domain, "A")
            return str(answers[0]) if answers else None
    except Exception:
        pass
    try:
        return socket.gethostbyname(domain)
    except Exception:
        return None


def _whois(domain: str, timeout: int = 15) -> dict[str, Any]:
    """WHOIS через системную команду whois. Возвращает {success, message, data, full_text}."""
    try:
        proc = subprocess.run(
            ["whois", domain],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (proc.stdout or "").strip()
        if not out:
            return {"success": False, "message": "Нет ответа WHOIS", "data": None, "full_text": None}
        data = {}
        full_text = out
        for line in out.splitlines():
            line = line.strip()
            if ":" in line and not line.startswith("%") and not line.startswith("#"):
                key, _, value = line.partition(":")
                key, value = key.strip(), value.strip()
                if key and value:
                    if key not in data:
                        data[key] = value
                    else:
                        if not isinstance(data[key], list):
                            data[key] = [data[key]]
                        data[key].append(value)
        return {"success": True, "message": "Данные получены", "data": data, "full_text": full_text}
    except FileNotFoundError:
        return {"success": False, "message": "Команда whois не найдена", "data": None, "full_text": None}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Таймаут WHOIS", "data": None, "full_text": None}
    except Exception as e:
        return {"success": False, "message": str(e)[:200], "data": None, "full_text": None}


def _dns_records(domain: str) -> dict[str, Any]:
    """DNS записи A, AAAA, NS, MX, TXT. Возвращает {success, records}."""
    if not dns:
        return {"success": False, "records": None}
    records = {}
    for rtype in ("A", "AAAA", "NS", "MX", "TXT"):
        try:
            answers = dns.resolver.resolve(domain, rtype)
            if rtype == "MX":
                records[rtype] = [{"host": str(r.exchange), "priority": r.preference} for r in answers]
            elif rtype == "TXT":
                records[rtype] = [r.to_text().strip('"') for r in answers]
            else:
                records[rtype] = [str(r) for r in answers]
        except Exception:
            pass
    return {"success": True, "records": records}


def _ssl_info(domain: str, timeout: int = 10) -> dict[str, Any]:
    """Информация об SSL-сертификате. Возвращает {success, is_valid, message, issuer, subject, valid_to, days_left}."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return {"success": False, "is_valid": False, "message": "Сертификат не получен"}
                from datetime import datetime
                issuer = dict(x[0] for x in cert.get("issuer", []))
                subject = dict(x[0] for x in cert.get("subject", []))
                not_after = cert.get("notAfter")
                issuer_s = issuer.get("organizationName", "") or issuer.get("commonName", "")
                subject_s = subject.get("commonName", "") or subject.get("organizationName", "")
                valid_to = not_after
                days_left = None
                if not_after:
                    try:
                        # Format: 'Feb 24 12:00:00 2026 GMT'
                        dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                        from datetime import timezone
                        days_left = (dt.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
                    except Exception:
                        pass
                return {
                    "success": True,
                    "is_valid": True,
                    "message": "Сертификат действителен",
                    "issuer": issuer_s,
                    "subject": subject_s,
                    "valid_to": valid_to,
                    "days_left": days_left,
                }
    except ssl.SSLCertVerificationError as e:
        return {"success": True, "is_valid": False, "message": f"Ошибка проверки: {e!s}"[:100]}
    except Exception as e:
        return {"success": False, "is_valid": False, "message": str(e)[:150]}


def _crtsh(domain: str, timeout: int = 20) -> dict[str, Any]:
    """Поддомены и имена из crt.sh API. Возвращает {success, message, names}."""
    if not requests:
        return {"success": False, "message": "requests не установлен", "names": []}
    try:
        # crt.sh: q=%.domain — поддомены; в URL % кодируется как %25
        url = "https://crt.sh/?q=%25." + domain + "&output=json"
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        names = set()
        for item in data if isinstance(data, list) else []:
            name = item.get("name_value") or item.get("common_name")
            if name:
                for n in name.replace(" ", "\n").split():
                    n = n.strip().lower()
                    if n and not n.startswith("*"):
                        names.add(n)
        names = sorted(names)[:100]
        return {"success": True, "message": f"Найдено записей: {len(names)}", "names": names}
    except Exception as e:
        return {"success": False, "message": str(e)[:80], "names": []}


class DomainSearch:
    """Поиск информации по домену. Без UI — только данные."""

    def __init__(self) -> None:
        self.resources = [
            ("SecurityTrails", "https://securitytrails.com/domain/{domain}"),
            ("Shodan", "https://www.shodan.io/search?query=hostname:{domain}"),
            ("VirusTotal", "https://www.virustotal.com/gui/domain/{domain}"),
            ("DNSdumpster", "https://dnsdumpster.com/"),
        ]
        self.ssl_resources = [
            ("SSL Labs", "https://www.ssllabs.com/ssltest/analyze.html?d={domain}"),
            ("Crt.sh", "https://crt.sh/?q={domain}"),
        ]

    def search(self, input_data: str, **kwargs: Any) -> dict[str, Any]:
        """
        Поиск по домену. Возвращает словарь для панели проекта:
        {success, error?, output (текст), sections? (структурированные данные)}
        """
        progress_callback = kwargs.get("progress_callback")

        def progress(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        is_valid, err = _validate_domain(input_data)
        if not is_valid:
            return {"success": False, "error": err or "Неверный домен", "output": ""}

        domain = _normalize_domain(input_data)
        lines = [f"Анализ домена: {domain}", ""]

        progress("Определение IP...")
        ip = _get_ip(domain)
        lines.append(f"IP адрес: {ip}" if ip else "IP адрес: не удалось определить")
        lines.append("")

        progress("WHOIS...")
        whois_info = _whois(domain)
        lines.append("=== WHOIS ===")
        if whois_info["success"] and whois_info.get("data"):
            for k, v in list(whois_info["data"].items())[:8]:
                if isinstance(v, list):
                    v = ", ".join(str(x) for x in v[:3])
                lines.append(f"  {k}: {v}")
            if whois_info.get("full_text"):
                lines.append("\nПолный текст WHOIS (фрагмент):")
                lines.append(whois_info["full_text"][:400] + "..." if len(whois_info["full_text"]) > 400 else whois_info["full_text"])
        else:
            lines.append(f"  {whois_info.get('message', 'Нет данных')}")
        lines.append("")

        progress("DNS...")
        dns_info = _dns_records(domain)
        lines.append("=== DNS записи ===")
        if dns_info.get("records"):
            rec = dns_info["records"]
            for typ, vals in rec.items():
                if vals:
                    lines.append(f"  {typ}: {vals}")
        else:
            lines.append("  DNS записи не получены (установите dnspython)")
        lines.append("")

        progress("SSL...")
        ssl_info = _ssl_info(domain)
        lines.append("=== SSL сертификат ===")
        if ssl_info.get("is_valid"):
            lines.append(f"  {ssl_info.get('message', '')}")
            if ssl_info.get("issuer"):
                lines.append(f"  Издатель: {ssl_info['issuer']}")
            if ssl_info.get("valid_to"):
                lines.append(f"  Действителен до: {ssl_info['valid_to']}")
            if ssl_info.get("days_left") is not None:
                lines.append(f"  Осталось дней: {ssl_info['days_left']}")
        else:
            lines.append(f"  {ssl_info.get('message', 'Сертификат не получен')}")
        lines.append("")

        progress("crt.sh...")
        crt = _crtsh(domain)
        lines.append("=== Сертификаты и поддомены (crt.sh) ===")
        if crt.get("names"):
            for name in crt["names"][:25]:
                lines.append(f"  • {name}")
            if len(crt["names"]) > 25:
                lines.append(f"  ... и ещё {len(crt['names']) - 25}")
        else:
            lines.append(f"  {crt.get('message', 'Нет данных')}")
        lines.append("")

        lines.append("=== Ссылки для доп. проверки ===")
        for name, url_tpl in self.resources + self.ssl_resources:
            lines.append(f"  {name}: {url_tpl.format(domain=domain)}")

        output = "\n".join(lines)
        return {"success": True, "output": output, "sections": {"domain": domain, "ip": ip}}


def run_domain_search(domain: str, progress_callback: Any = None) -> dict[str, Any]:
    """
    Точка входа для вызова из бэкенда панели.
    domain — строка с доменом (можно с https://).
    progress_callback(message: str) — опционально.
    """
    ds = DomainSearch()
    return ds.search(domain, progress_callback=progress_callback)
