#!/usr/bin/env python3
"""
Главный файл запуска OSINT Panel.
Запуск: python run.py  (или python3 run.py)
Работает одинаково на Windows, Linux и macOS.
"""
import os
import sys
import subprocess

# Переход в папку проекта (где лежит run.py)
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# Подключение backend
sys.path.insert(0, os.path.join(ROOT, "backend"))


def ensure_deps():
    """Устанавливает зависимости, если Flask не найден (все инструменты — из requirements.txt)."""
    try:
        import flask
    except ImportError:
        print("Устанавливаю зависимости...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])


def get_lan_ip():
    """Примерный IP в локальной сети (для подсказки)."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def main():
    ensure_deps()
    port = 5000
    print("Панель запущена.")
    print("  На этом ПК:      http://127.0.0.1:{}".format(port))
    lan = get_lan_ip()
    if lan:
        print("  В локальной сети: http://{}:{}  (откройте с другого устройства)".format(lan, port))
    else:
        print("  В локальной сети: http://<IP этого ПК>:{}  (узнайте IP: ip addr или ifconfig)".format(port))
    print("  Если с другого устройства не открывается — разрешите порт {} в фаерволе.".format(port))
    from app import app
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
