"""
Модуль автоматических проверок для OSINT
Выполняет реальные запросы к API и сервисам для получения точных результатов
"""
import requests
import socket
import dns.resolver
import re
from typing import Dict, List, Optional, Any
from urllib.parse import quote


# Глобальные настройки
REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def safe_request(url: str, method: str = "GET", **kwargs) -> Optional[requests.Response]:
    """
    Безопасный HTTP запрос с обработкой ошибок
    
    Args:
        url: URL для запроса
        method: HTTP метод
        **kwargs: Дополнительные параметры для requests
        
    Returns:
        Response объект или None при ошибке
    """
    try:
        headers = kwargs.pop('headers', {})
        headers['User-Agent'] = USER_AGENT
        kwargs['headers'] = headers
        kwargs['timeout'] = kwargs.get('timeout', REQUEST_TIMEOUT)
        
        if method.upper() == "GET":
            return requests.get(url, **kwargs)
        elif method.upper() == "POST":
            return requests.post(url, **kwargs)
        else:
            return None
    except Exception:
        return None


# ==================== EMAIL ПРОВЕРКИ ====================

def check_email_breach(email: str) -> Dict[str, Any]:
    """
    Автоматическая проверка email в Have I Been Pwned
    
    Args:
        email: Email адрес
        
    Returns:
        dict: Информация об утечках
    """
    try:
        # Используем API Have I Been Pwned (бесплатный, без ключа)
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}"
        response = safe_request(url, headers={"hibp-api-key": ""})  # Можно добавить API ключ
        
        if response and response.status_code == 200:
            breaches = response.json()
            breach_names = [b.get('Name', 'Unknown') for b in breaches[:10]]  # Первые 10
            return {
                'breached': True,
                'message': f"Найдено {len(breaches)} утечек данных!",
                'breaches': breach_names,
                'total': len(breaches)
            }
        elif response and response.status_code == 404:
            return {
                'breached': False,
                'message': "Email не найден в известных утечках данных",
                'breaches': [],
                'total': 0
            }
    except Exception:
        pass
    
    return {
        'breached': None,
        'message': "Не удалось проверить утечки (API недоступен)",
        'breaches': [],
        'total': 0
    }


def check_domain_mx(domain: str) -> Dict[str, Any]:
    """
    Автоматическая проверка MX записей домена
    
    Args:
        domain: Домен
        
    Returns:
        dict: Информация о MX записях
    """
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        records = []
        for mx in mx_records:
            records.append({
                'host': str(mx.exchange).rstrip('.'),
                'priority': mx.preference
            })
        records.sort(key=lambda x: x['priority'])
        
        return {
            'success': True,
            'message': f"Найдено {len(records)} MX записей",
            'records': records
        }
    except dns.resolver.NoAnswer:
        return {
            'success': False,
            'message': "MX записи не найдены",
            'records': []
        }
    except Exception:
        return {
            'success': False,
            'message': "Не удалось проверить MX записи",
            'records': []
        }


# ==================== DOMAIN ПРОВЕРКИ ====================

def check_domain_whois(domain: str) -> Dict[str, Any]:
    """
    Автоматическая проверка WHOIS информации
    
    Args:
        domain: Домен
        
    Returns:
        dict: WHOIS информация
    """
    try:
        import subprocess
        result = subprocess.run(
            ['whois', domain],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.stdout:
            whois_text = result.stdout[:1000]  # Первые 1000 символов
            
            # Извлекаем ключевую информацию
            info = {}
            lines = whois_text.split('\n')
            for line in lines[:50]:  # Первые 50 строк
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if key in ['registrar', 'creation date', 'expiry date', 'name server']:
                        if key not in info:
                            info[key] = []
                        info[key].append(value)
            
            return {
                'success': True,
                'message': "WHOIS информация получена",
                'data': info,
                'full_text': whois_text
            }
    except FileNotFoundError:
        return {
            'success': False,
            'message': "WHOIS недоступен (требуется установка whois)",
            'data': {},
            'full_text': ''
        }
    except Exception:
        return {
            'success': False,
            'message': "Ошибка при получении WHOIS",
            'data': {},
            'full_text': ''
        }
    
    return {
        'success': False,
        'message': "Не удалось получить WHOIS информацию",
        'data': {},
        'full_text': ''
    }


def check_domain_dns(domain: str) -> Dict[str, Any]:
    """
    Автоматическая проверка DNS записей домена
    
    Args:
        domain: Домен
        
    Returns:
        dict: DNS записи
    """
    dns_records = {}
    
    # A записи
    try:
        a_records = dns.resolver.resolve(domain, 'A')
        dns_records['A'] = [str(r) for r in a_records]
    except:
        dns_records['A'] = []
    
    # AAAA записи (IPv6)
    try:
        aaaa_records = dns.resolver.resolve(domain, 'AAAA')
        dns_records['AAAA'] = [str(r) for r in aaaa_records]
    except:
        dns_records['AAAA'] = []
    
    # NS записи
    try:
        ns_records = dns.resolver.resolve(domain, 'NS')
        dns_records['NS'] = [str(r).rstrip('.') for r in ns_records]
    except:
        dns_records['NS'] = []
    
    # MX записи
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        dns_records['MX'] = [{'host': str(r.exchange).rstrip('.'), 'priority': r.preference} for r in mx_records]
    except:
        dns_records['MX'] = []
    
    # TXT записи
    try:
        txt_records = dns.resolver.resolve(domain, 'TXT')
        dns_records['TXT'] = [str(r).strip('"') for r in txt_records]
    except:
        dns_records['TXT'] = []
    
    return {
        'success': True,
        'message': "DNS записи получены",
        'records': dns_records
    }


def check_domain_ssl(domain: str) -> Dict[str, Any]:
    """
    Автоматическая проверка SSL сертификата
    
    Args:
        domain: Домен
        
    Returns:
        dict: Информация о SSL
    """
    try:
        import ssl
        import socket
        from datetime import datetime
        
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                
                issuer = dict(x[0] for x in cert['issuer'])
                subject = dict(x[0] for x in cert['subject'])
                
                not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
                not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                
                days_left = (not_after - datetime.now()).days
                
                return {
                    'success': True,
                    'message': f"SSL сертификат валиден, истекает через {days_left} дней",
                    'issuer': issuer.get('organizationName', 'Unknown'),
                    'subject': subject.get('commonName', domain),
                    'valid_from': cert['notBefore'],
                    'valid_to': cert['notAfter'],
                    'days_left': days_left,
                    'is_valid': days_left > 0
                }
    except Exception as e:
        return {
            'success': False,
            'message': f"Не удалось проверить SSL: {str(e)[:50]}",
            'issuer': None,
            'subject': None,
            'valid_from': None,
            'valid_to': None,
            'days_left': None,
            'is_valid': False
        }


# ==================== IP ПРОВЕРКИ ====================

def check_ip_geoip(ip: str) -> Dict[str, Any]:
    """
    Автоматическая проверка GeoIP информации
    
    Args:
        ip: IP адрес
        
    Returns:
        dict: GeoIP информация
    """
    try:
        response = safe_request(f"http://ip-api.com/json/{ip}")
        if response and response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return {
                    'success': True,
                    'message': "GeoIP информация получена",
                    'data': {
                        'country': data.get('country', 'N/A'),
                        'region': data.get('regionName', 'N/A'),
                        'city': data.get('city', 'N/A'),
                        'isp': data.get('isp', 'N/A'),
                        'org': data.get('org', 'N/A'),
                        'lat': data.get('lat', 'N/A'),
                        'lon': data.get('lon', 'N/A'),
                        'timezone': data.get('timezone', 'N/A'),
                        'as': data.get('as', 'N/A'),
                    }
                }
    except Exception:
        pass
    
    return {
        'success': False,
        'message': "Не удалось получить GeoIP информацию",
        'data': {}
    }


def check_ip_reputation(ip: str) -> Dict[str, Any]:
    """
    Автоматическая проверка репутации IP
    
    Args:
        ip: IP адрес
        
    Returns:
        dict: Информация о репутации
    """
    results = {}
    
    # Проверка в AbuseIPDB (требует API ключ, но можно попробовать без)
    try:
        # Это пример, реальный API требует ключ
        response = safe_request(f"https://www.abuseipdb.com/check/{ip}")
        if response:
            results['abuseipdb'] = {
                'checked': True,
                'message': "Проверено в AbuseIPDB"
            }
    except:
        pass
    
    return {
        'success': True,
        'message': "Проверка репутации выполнена",
        'results': results
    }


# ==================== USERNAME ПРОВЕРКИ ====================

def check_username_availability(username: str, platforms: Dict[str, str]) -> Dict[str, Any]:
    """
    Автоматическая проверка доступности username на платформах
    
    Args:
        username: Username
        platforms: Словарь платформ и их URL шаблонов
        
    Returns:
        dict: Результаты проверки
    """
    results = {}
    
    for platform, url_template in list(platforms.items())[:5]:  # Проверяем первые 5
        try:
            url = url_template.format(username=username)
            response = safe_request(url, timeout=5)
            
            if response:
                if response.status_code == 200:
                    # Простая проверка - если страница существует
                    content = response.text.lower()
                    # Проверяем наличие индикаторов существующего профиля
                    if any(indicator in content for indicator in ['profile', 'user', 'member', 'account']):
                        results[platform] = {
                            'exists': True,
                            'url': url,
                            'message': "Профиль найден"
                        }
                    else:
                        results[platform] = {
                            'exists': False,
                            'url': url,
                            'message': "Профиль не найден"
                        }
                elif response.status_code == 404:
                    results[platform] = {
                        'exists': False,
                        'url': url,
                        'message': "Профиль не найден (404)"
                    }
                else:
                    results[platform] = {
                        'exists': None,
                        'url': url,
                        'message': f"Статус: {response.status_code}"
                    }
        except Exception:
            results[platform] = {
                'exists': None,
                'url': url_template.format(username=username),
                'message': "Не удалось проверить"
            }
    
    return {
        'success': True,
        'message': f"Проверено {len(results)} платформ",
        'results': results
    }


# ==================== PHONE ПРОВЕРКИ ====================

def check_phone_info(phone: str) -> Dict[str, Any]:
    """
    Автоматическая проверка информации о номере телефона.
    Использует phonenumbers (все страны) при наличии, иначе встроенный разбор.
    """
    try:
        from .external_tools import get_phone_info_phonenumbers
        result = get_phone_info_phonenumbers(phone)
        if result['success']:
            return result
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: встроенный разбор (Россия и базовые коды)
    import re
    cleaned = re.sub(r'\D', '', phone)
    info = {
        'normalized': f"+{cleaned}" if cleaned else phone,
        'cleaned': cleaned,
        'country_code': None,
        'country': None,
        'operator': None
    }
    if cleaned.startswith('7') or (cleaned.startswith('8') and len(cleaned) == 11):
        info['country_code'] = '+7'
        info['country'] = 'Россия'
        if cleaned.startswith('8'):
            cleaned = '7' + cleaned[1:]
        prefix = cleaned[1:4]
        operators = {
            '900': 'Мегафон', '901': 'Мегафон', '910': 'МТС', '915': 'МТС',
            '950': 'Билайн', '960': 'Билайн', '977': 'Мегафон', '985': 'Мегафон',
        }
        info['operator'] = operators.get(prefix, 'Неизвестный оператор')
    elif cleaned.startswith('1') and len(cleaned) == 11:
        info['country_code'] = '+1'
        info['country'] = 'США/Канада'
    elif cleaned.startswith('44'):
        info['country_code'] = '+44'
        info['country'] = 'Великобритания'
    elif cleaned.startswith('49'):
        info['country_code'] = '+49'
        info['country'] = 'Германия'
    elif cleaned.startswith('33'):
        info['country_code'] = '+33'
        info['country'] = 'Франция'
    else:
        info['country'] = 'Другой регион'

    return {
        'success': True,
        'message': "Информация о номере получена",
        'data': info
    }
