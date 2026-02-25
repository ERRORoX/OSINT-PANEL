"""
Состояние приложения: идентификаторы вкладок и названия.
Вынесено в отдельный модуль, чтобы не дублировать константы и избежать рассинхрона.
"""
TAB_IDS = (
    "email", "domain", "username", "ip", "phone", "instagram",
    "vin", "inn", "telegram", "image", "anonsms", "set"
)
TAB_NAMES = {
    "email": "Email",
    "domain": "Домен",
    "username": "Username",
    "ip": "IP",
    "phone": "Телефон",
    "instagram": "Instagram",
    "vin": "VIN/Авто",
    "inn": "ИНН/ОГРН",
    "telegram": "Telegram",
    "image": "Поиск по фото",
    "anonsms": "Анонимные СМС",
    "set": "SET",
}
