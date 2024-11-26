import json
from typing import Any, Dict, List
from datetime import datetime, date, time
from decimal import Decimal
import hashlib
import secrets
from pathlib import Path

class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for complex types"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.strftime('%H:%M')
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)

def generate_random_string(length: int = 32) -> str:
    """Generate random string"""
    return secrets.token_hex(length // 2)

def hash_string(s: str) -> str:
    """Generate hash from string"""
    return hashlib.sha256(s.encode()).hexdigest()

def format_money(amount: Decimal) -> str:
    """Format money amount"""
    return f"{amount:,.2f} сум"

def format_phone(phone: str) -> str:
    """Format phone number"""
    phone = phone.replace('+', '')
    if phone.startswith('998'):
        return f"+{phone[:3]} {phone[3:5]} {phone[5:8]} {phone[8:]}"
    if phone.startswith('7'):
        return f"+{phone[:1]} {phone[1:4]} {phone[4:7]} {phone[7:]}"
    return phone

def group_by(items: List[Dict], key: str) -> Dict[Any, List[Dict]]:
    """Group list of dicts by key"""
    result = {}
    for item in items:
        k = item.get(key)
        if k not in result:
            result[k] = []
        result[k].append(item)
    return result

def chunk_list(lst: List, n: int) -> List[List]:
    """Split list into chunks"""
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def deep_update(d: dict, u: dict) -> dict:
    """Deep update dict"""
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def strip_html(text: str) -> str:
    """Remove HTML tags from text"""
    import re
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def truncate(text: str, length: int) -> str:
    """Truncate text to length"""
    return text[:length] + '...' if len(text) > length else text

def parse_bool(value: Any) -> bool:
    """Parse boolean value"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 't', 'y', 'yes')
    return bool(value)