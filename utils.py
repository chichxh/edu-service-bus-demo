from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# --- Пути к данным -----------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"

DB_USERS_V1 = DATA_DIR / "users.v1.json"
DB_USERS_LEGACY = DATA_DIR / "users.json"

DB_INVENTORY_V1 = DATA_DIR / "inventory.v1.json"
DB_INVENTORY_LEGACY = DATA_DIR / "inventory.json"

LOG_FILE = DATA_DIR / "events.log"


# --- Вспомогательные функции -------------------------------------------------

def _now_iso() -> str:
    """Текущее время в ISO8601 UTC."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write(path: Path, obj: Any) -> None:
    """
    Атомарная запись JSON: пишем во временный файл и заменяем.
    Безопасно при падениях между записью и заменой.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def save_json(path: str | Path, data: Any) -> None:
    """Сохранить произвольный объект в JSON с атомарной записью."""
    _atomic_write(Path(path), data)


def load_json(path: str | Path, default: Any = None) -> Any:
    """Загрузить JSON. Если файла нет — вернуть default (или {})."""
    p = Path(path)
    if not p.exists():
        return {} if default is None else default
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def log_action(service: str, event: str, payload: Optional[dict] = None) -> None:
    """
    Простейший логгер: пишет JSON-строку в data/events.log и дублирует в stdout.
    """
    entry = {
        "ts": _now_iso(),
        "service": service,
        "event": event,
        "payload": payload or {},
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[{entry['ts']}] {service}: {event}")


# --- Опознание схемы и индексы ----------------------------------------------

def _is_v1_users(db: dict) -> bool:
    return isinstance(db, dict) and isinstance(db.get("users"), dict)


def _is_legacy_users(db: dict) -> bool:
    return isinstance(db, dict) and isinstance(db.get("users"), list)


def _is_v1_inventory(db: dict) -> bool:
    return isinstance(db, dict) and isinstance(db.get("items"), dict)


def _is_legacy_inventory(db: dict) -> bool:
    return isinstance(db, dict) and isinstance(db.get("warehouse"), dict)


def _touch_meta(db: Dict[str, Any]) -> None:
    db.setdefault("meta", {})
    db["meta"].setdefault("version", 1)
    db["meta"]["updated_at"] = _now_iso()


def _build_users_indexes(users: Dict[str, dict]) -> Dict[str, Dict[str, str]]:
    by_username: Dict[str, str] = {}
    by_email: Dict[str, str] = {}
    for uid, u in users.items():
        un = u.get("username")
        em = u.get("email")
        if un:
            by_username[un] = uid
        if em:
            by_email[em] = uid
    return {"by_username": by_username, "by_email": by_email}


def _build_inventory_indexes(items: Dict[str, dict]) -> Dict[str, Dict[str, str]]:
    by_name: Dict[str, str] = {}
    for sku, it in items.items():
        name = it.get("name")
        if name:
            by_name[name] = sku
    return {"by_name": by_name}


# --- Миграция legacy -> v1 (в память) ---------------------------------------

def _gen_id(prefix: str, n: int) -> str:
    return f"{prefix}_{n:04d}"


def _migrate_users_legacy_to_v1(src: dict) -> dict:
    """
    Преобразует legacy users.json вида:
      { "users": [{username,email,password}, ...], "accounts": {username:{balance}} }
    в v1-структуру:
      { "users": {usr_0001: {...}}, "indexes": {...}, "meta": {...} }
    """
    users_list = src.get("users", []) or []
    accounts = src.get("accounts", {}) or {}

    users_out: Dict[str, dict] = {}
    for i, u in enumerate(users_list, start=1):
        uid = _gen_id("usr", i)
        username = u.get("username")
        email = u.get("email")
        password = u.get("password")
        acc = accounts.get(username, {})
        if isinstance(acc, dict):
            balance = acc.get("balance", 0)
        elif isinstance(acc, (int, float)):
            balance = int(acc)
        else:
            balance = 0

        users_out[uid] = {
            "username": username,
            "email": email,
            "role": "user",
            # переносим как есть; хэширование — на уровне бизнес-логики при обновлении
            "password_hash": password,
            "status": "active",
            "account": {"balance": balance, "currency": "RUB"},
            "profile": {"first_name": None, "last_name": None, "phone": None},
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "deleted_at": None,
        }

    migrated = {
        "meta": {"version": 1, "updated_at": _now_iso()},
        "users": users_out,
        "indexes": _build_users_indexes(users_out),
    }
    return migrated


def _migrate_inventory_legacy_to_v1(src: dict) -> dict:
    """
    Преобразует legacy inventory.json вида:
      { "warehouse": {name:{price,stock,reserved}} }
    в v1-структуру:
      { "items": {sku_0001: {...}}, "indexes": {...}, "reservations": {}, "meta": {...} }
    """
    wh = src.get("warehouse", {}) or {}

    items_out: Dict[str, dict] = {}
    for i, (name, data) in enumerate(wh.items(), start=1):
        sku = _gen_id("sku", i)
        items_out[sku] = {
            "name": name,
            "price": data.get("price", 0),
            "stock": {
                "on_hand": data.get("stock", 0),
                "reserved": data.get("reserved", 0),
            },
            "status": "active",
            "category": None,
            "attributes": {},
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "deleted_at": None,
        }

    migrated = {
        "meta": {"version": 1, "updated_at": _now_iso()},
        "items": items_out,
        "indexes": _build_inventory_indexes(items_out),
        "reservations": {},
    }
    return migrated


# --- Загрузка БД -------------------------------------------------------------

def load_users_db(prefer_v1: bool = True) -> dict:
    """
    Загрузить БД пользователей.
    - Если существует users.v1.json — вернуть её.
    - Иначе, если есть legacy users.json:
        * при prefer_v1=True — вернуть ОТМИГРИРОВАННЫЙ в v1 объект (в память);
        * при prefer_v1=False — вернуть как есть (legacy).
    """
    if DB_USERS_V1.exists():
        return load_json(DB_USERS_V1, default={})
    legacy = load_json(DB_USERS_LEGACY, default={})
    if not legacy:
        # пустая в1-заготовка
        return {"meta": {"version": 1, "updated_at": _now_iso()}, "users": {}, "indexes": {"by_username": {}, "by_email": {}}}
    return _migrate_users_legacy_to_v1(legacy) if prefer_v1 else legacy


def load_inventory_db(prefer_v1: bool = True) -> dict:
    """
    Загрузить БД склада.
    - Если существует inventory.v1.json — вернуть её.
    - Иначе, если есть legacy inventory.json:
        * при prefer_v1=True — вернуть ОТМИГРИРОВАННЫЙ в v1 объект (в память);
        * при prefer_v1=False — вернуть как есть (legacy).
    """
    if DB_INVENTORY_V1.exists():
        return load_json(DB_INVENTORY_V1, default={})
    legacy = load_json(DB_INVENTORY_LEGACY, default={})
    if not legacy:
        # пустая в1-заготовка
        return {"meta": {"version": 1, "updated_at": _now_iso()}, "items": {}, "indexes": {"by_name": {}}, "reservations": {}}
    return _migrate_inventory_legacy_to_v1(legacy) if prefer_v1 else legacy


# --- Сохранение БД -----------------------------------------------------------

def _ensure_users_indexes(db: dict) -> None:
    if not _is_v1_users(db):
        return
    db["indexes"] = _build_users_indexes(db.get("users", {}))


def _ensure_inventory_indexes(db: dict) -> None:
    if not _is_v1_inventory(db):
        return
    db["indexes"] = _build_inventory_indexes(db.get("items", {}))


def save_users_db(data: dict) -> Path:
    """
    Сохранить БД пользователей.
    - Если это v1-объект — пишет в users.v1.json (обновляет meta и индексы).
    - Если это legacy-объект — ПРЕОБРАЗУЕТ в v1 и пишет в users.v1.json.
    Возвращает путь к сохранённому файлу.
    """
    if _is_legacy_users(data):
        data = _migrate_users_legacy_to_v1(data)
    elif _is_v1_users(data):
        _ensure_users_indexes(data)
        _touch_meta(data)
    else:
        # На всякий случай нормализуем к пустой v1
        data = {"meta": {"version": 1, "updated_at": _now_iso()}, "users": {}, "indexes": {"by_username": {}, "by_email": {}}}

    save_json(DB_USERS_V1, data)
    return DB_USERS_V1


def save_inventory_db(data: dict) -> Path:
    """
    Сохранить БД склада.
    - Если это v1-объект — пишет в inventory.v1.json (обновляет meta и индексы).
    - Если это legacy-объект — ПРЕОБРАЗУЕТ в v1 и пишет в inventory.v1.json.
    Возвращает путь к сохранённому файлу.
    """
    if _is_legacy_inventory(data):
        data = _migrate_inventory_legacy_to_v1(data)
    elif _is_v1_inventory(data):
        _ensure_inventory_indexes(data)
        _touch_meta(data)
    else:
        data = {"meta": {"version": 1, "updated_at": _now_iso()}, "items": {}, "indexes": {"by_name": {}}, "reservations": {}}

    save_json(DB_INVENTORY_V1, data)
    return DB_INVENTORY_V1


# --- Утилиты для работы с ID ----------------------------------

def users_next_id(db: dict) -> str:
    """Подбор следующего usr_XXXX на основе уже существующих ключей."""
    if not _is_v1_users(db):
        return _gen_id("usr", 1)
    users = db.get("users", {})
    max_num = 0
    for uid in users.keys():
        if isinstance(uid, str) and uid.startswith("usr_"):
            try:
                n = int(uid.split("_", 1)[1])
                max_num = max(max_num, n)
            except Exception:
                pass
    return _gen_id("usr", max_num + 1)


def inventory_next_sku(db: dict) -> str:
    """Подбор следующего sku_XXXX на основе уже существующих ключей."""
    if not _is_v1_inventory(db):
        return _gen_id("sku", 1)
    items = db.get("items", {})
    max_num = 0
    for sku in items.keys():
        if isinstance(sku, str) and sku.startswith("sku_"):
            try:
                n = int(sku.split("_", 1)[1])
                max_num = max(max_num, n)
            except Exception:
                pass
    return _gen_id("sku", max_num + 1)



# --- Утилиты для работы с сессией --------------------------

SESSION_FILE = DATA_DIR / "session.json"  # текущая авторизованная сессия пользователя

def save_session(user_id: str, user_obj: dict, source: str = "login") -> Path:
    payload = {
        "user_id": user_id,
        "username": user_obj.get("username"),
        "email": user_obj.get("email"),
        "role": user_obj.get("role", "user"),
        "login_at": _now_iso(),
        "source": source,
    }
    save_json(SESSION_FILE, payload)
    log_action("Session", "session_saved", {"user_id": user_id, "username": payload["username"], "role": payload["role"]})
    return SESSION_FILE

def load_session(default: dict | None = None) -> dict | None:
    if not SESSION_FILE.exists():
        return default
    return load_json(SESSION_FILE, default=default)

def clear_session() -> None:
    if SESSION_FILE.exists():
        os.remove(SESSION_FILE)
        log_action("Session", "session_cleared")

def get_current_user(db: dict | None = None) -> tuple[str | None, dict | None]:
    sess = load_session()
    if not sess: return None, None
    uid = sess.get("user_id")
    if not uid: return None, None
    db = db or load_users_db()
    return uid, (db.get("users", {}).get(uid) if db else None)

def current_user_is_admin(db: dict | None = None) -> bool:
    uid, user = get_current_user(db)
    return bool(user and user.get("role") == "admin")


# --- Примеры CRUD-хелперов ---------------------------------
# Эти функции могут пригодиться сервисам. Они НЕ используются внутри utils.

def users_upsert(db: dict, uid: Optional[str], user_obj: dict) -> str:
    """
    Создать или обновить пользователя в v1-структуре.
    Если uid не задан — генерируется новый.
    """
    if not _is_v1_users(db):
        raise ValueError("users_upsert ожидает v1-схему users")
    db.setdefault("users", {})
    if not uid:
        uid = users_next_id(db)
    user_obj.setdefault("created_at", _now_iso())
    user_obj["updated_at"] = _now_iso()
    db["users"][uid] = user_obj
    _ensure_users_indexes(db)
    return uid


def inventory_upsert_item(db: dict, sku: Optional[str], item_obj: dict) -> str:
    """
    Создать или обновить товар в v1-структуре.
    Если sku не задан — генерируется новый.
    """
    if not _is_v1_inventory(db):
        raise ValueError("inventory_upsert_item ожидает v1-схему inventory")
    db.setdefault("items", {})
    if not sku:
        sku = inventory_next_sku(db)
    item_obj.setdefault("created_at", _now_iso())
    item_obj["updated_at"] = _now_iso()
    db["items"][sku] = item_obj
    _ensure_inventory_indexes(db)
    return sku
