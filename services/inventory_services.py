import uuid

from utils import log_action, load_inventory_db, save_inventory_db, inventory_upsert_item, current_user_is_admin
 
class InventoryService: 
    """Управление складом"""
    def __init__(self):
        # Эфемерные (на время процесса) списки для выбора по номеру
        self._lists = {}  # list_id -> [sku1, sku2, ...]

    def handle(self, data): 
        action = data.get("action") 
        if action == "check_item": 
            db = load_inventory_db()
            items = db.get("items", {})
            sku = data.get("sku")
            qty = data.get("qty")
            log_action("InventoryService", "check_item_requested", {"sku": sku, "qty": qty})

            name = data.get("item").get("name")
            sku = data.get("item").get("sku")
            qty = data.get("item").get("qty")
            order_id = data.get("order_id")
            payment_id = data.get("payment_id")
            user_id = data.get("user_id")

            it = items.get(sku)
            on_hand = it.get("stock").get("on_hand")

            if on_hand < qty:
                print(f"[InventoryService] Недостаточно товара '{name}' на складе (есть {on_hand}, нужно {qty}).")
                self.bus.publish("ProductOutOfStock", {"action": "notify_out_of_stock", "sku": sku, "qty": qty})
                log_action("InventoryService", "product_out_of_stock_published", {"sku": sku, "qty": qty, "order_id": order_id})
                return None
            else:
                print(f"[InventoryService] Товар в наличии.")
                self.bus.publish("ProductInStock", {"action": "reserve_item", "sku": sku, "qty": qty, "name": name, 
                                                    "order_id": order_id, "payment_id": payment_id, "user_id": user_id})
                log_action("InventoryService", "product_in_stock_published", {"sku": sku, "qty": qty, "order_id": order_id})
                return None
            

        elif action == "reserve_item":
            # Поддержим оба формата полезной нагрузки:
            # 1) sku/qty на корне
            # 2) item = {"sku": ..., "qty": ...}
            item = (data or {}).get("item") or {}
            sku = (data or {}).get("sku") or item.get("sku")
            qty = (data or {}).get("qty") or item.get("qty") or 0
            order_id = (data or {}).get("order_id")
            user_id = (data or {}).get("user_id")
            payment_id = (data or {}).get("payment_id")

            # Валидация
            try:
                qty = int(qty)
            except Exception:
                qty = 0

            if not sku or qty <= 0:
                print("[InventoryService] reserve_item: некорректные sku/qty.")
                log_action("InventoryService", "reserve_item_invalid_args", {"sku": sku, "qty": qty, "order_id": order_id})
                return

            db = load_inventory_db()
            items = db.get("items") or {}
            it = items.get(sku)

            if not it or it.get("status") == "deleted":
                print(f"[InventoryService] reserve_item: товар {sku} не найден.")
                log_action("InventoryService", "reserve_item_not_found", {"sku": sku, "qty": qty, "order_id": order_id})
                self.bus.publish("ProductOutOfStock", {
                    "action": "notify",
                    "reason": "not_found",
                    "sku": sku,
                    "requested_qty": qty,
                    "order_id": order_id,
                })
                return

            stock = it.get("stock") or {}
            on_hand = int(stock.get("on_hand", 0))
            reserved = int(stock.get("reserved", 0))
            available = on_hand - reserved

            # Резервируем
            it["stock"]["reserved"] = reserved + qty
            log_action("InventoryService", "reserve_applied", {"sku": sku, "qty": qty, "order_id": order_id})

            # На далекое будущее: Фиксируем резервацию в журнале резерваций
            # res_id = uuid.uuid4().hex  # простой уникальный идентификатор
            # db.setdefault("reservations", {})
            # db["reservations"][res_id] = {
            #     "reservation_id": res_id,
            #     "order_id": order_id,
            #     "payment_id": payment_id,
            #     "sku": sku,
            #     "qty": qty,
            #     "status": "reserved",        # будущие статусы: "fulfilled"/"canceled"/"expired"
            #     "created_at": None,          # можно вставить utils._now_iso() если вынесете в utils публично
            # }

            save_inventory_db(db)

            log_action("InventoryService", "reserve_item_ok", {
                # "reservation_id": res_id, "order_id": order_id, "sku": sku, "qty": qty,
                "reserved_total": reserved + qty
            })
            print(f"[InventoryService] Зарезервировано: sku={sku}, qty={qty}")

            amount = (it.get("price") or 0) * qty

            self.bus.publish("PaymentRequested", {
                "action": "charge",
                # "reservation_id": res_id,
                "payment_id": payment_id,
                "order_id": order_id,
                "user_id": user_id,
                "item": [{"sku": sku, "name": it.get("name"), "qty": qty, "price": it.get("price")}],
                "amount": amount,
                "currency": "RUB"  # при необходимости другое
            })
            log_action("InventoryService", "payment_requested_published", {"order_id": order_id, "payment_id": payment_id, "sku": sku, "qty": qty})
            return

        elif action == "list_items_old":
            db = load_inventory_db()
            items = db.get("items", {})
            print("[InventoryService] Товары на складе:")
            print("Выбор | Название                 | Цена   | В наличии")
            print("-"*68)
            count = 0
            for sku, it in items.items():
                count += 1
                name = it.get("name", "")
                price = it.get("price", 0)
                on_hand = it.get("stock", {}).get("on_hand", 0)
                reserved = it.get("stock", {}).get("reserved", 0)
                print(f"{count:<5} | {name:<24} | {price:>7} | {on_hand:>9}")

        elif action == "list_items":
            return self._handle_list_items(data)
        
        elif action == "list_resolve":
            # Опционально: если хочется резолвить индекс через сервис
            list_id = data.get("list_id")
            index = int(data.get("index", 0))
            skus = self._lists.get(list_id) or []
            if 1 <= index <= len(skus):
                return {"sku": skus[index-1]}
            log_action("InventoryService", "list_resolve", {"list_id": list_id, "index": index})
            return {"sku": None}

        elif action == "list_items_full":
            db = load_inventory_db()
            items = db.get("items", {})
            print("[InventoryService] Товары на складе:")
            print("SKU       | Название                 | Цена | В наличии | Резерв")
            print("-"*68)
            for sku, it in items.items():
                name = it.get("name", "")
                price = it.get("price", 0)
                on_hand = it.get("stock", {}).get("on_hand", 0)
                reserved = it.get("stock", {}).get("reserved", 0)
                print(f"{sku:<9} | {name:<24} | {price:>7} | {on_hand:>9} | {reserved:>6}")
            log_action("InventoryService", "list_items_full_printed", {"count": len(items)})

        elif action == "release_reservation":
            # Снять резерв (например, при неуспешной оплате)
            item = (data or {}).get("item") or {}
            sku = (data or {}).get("sku") or item.get("sku")
            qty = int((data or {}).get("qty") or item.get("qty") or 0)
            order_id = (data or {}).get("order_id")

            if not sku or qty <= 0:
                print("[InventoryService] release_reservation: некорректные sku/qty.")
                log_action("InventoryService", "release_invalid_args", {"sku": sku, "qty": qty, "order_id": order_id})
                return

            db = load_inventory_db()
            it = (db.get("items") or {}).get(sku)
            if not it or it.get("status") == "deleted":
                print(f"[InventoryService] release_reservation: товар {sku} не найден.")
                log_action("InventoryService", "release_not_found", {"sku": sku, "qty": qty, "order_id": order_id})
                return
            stock = it.get("stock") or {}
            reserved = int(stock.get("reserved", 0))
            new_reserved = max(0, reserved - qty)
            it["stock"]["reserved"] = new_reserved

            save_inventory_db(db)
            log_action("InventoryService", "reservation_released", {
                "sku": sku, "qty": qty, "order_id": order_id,
                "reserved_before": reserved, "reserved_after": new_reserved
            })
            return

        elif action == "commit_reservation":
            # Зафиксировать резерв при успешной оплате:
            # уменьшить reserved на qty и списать qty из on_hand
            item = (data or {}).get("item") or {}
            sku = (data or {}).get("sku") or item.get("sku")
            qty = int((data or {}).get("qty") or item.get("qty") or 0)
            order_id = (data or {}).get("order_id")

            if not sku or qty <= 0:
                print("[InventoryService] commit_reservation: некорректные sku/qty.")
                log_action("InventoryService", "commit_invalid_args", {"sku": sku, "qty": qty, "order_id": order_id})
                return

            db = load_inventory_db()
            it = (db.get("items") or {}).get(sku)
            if not it or it.get("status") == "deleted":
                print(f"[InventoryService] commit_reservation: товар {sku} не найден.")
                log_action("InventoryService", "commit_not_found", {"sku": sku, "qty": qty, "order_id": order_id})
                return

            stock = it.get("stock") or {}
            on_hand = int(stock.get("on_hand", 0))
            reserved = int(stock.get("reserved", 0))

            # Нормализуем qty, чтобы не уйти в минус по резерву
            apply_qty = min(qty, reserved)
            new_reserved = reserved - apply_qty
            new_on_hand = max(0, on_hand - apply_qty)

            it["stock"]["reserved"] = new_reserved
            it["stock"]["on_hand"] = new_on_hand
            save_inventory_db(db)

            log_action("InventoryService", "reservation_committed", {
                "sku": sku, "qty": apply_qty, "order_id": order_id,
                "reserved_before": reserved, "reserved_after": new_reserved,
                "on_hand_before": on_hand, "on_hand_after": new_on_hand
            })
            return

    def _handle_list_items(self, data: dict):
        db = load_inventory_db()
        items_dict = db.get("items", {})
        items = []
        for sku, it in items_dict.items():
            items.append({
                "sku": sku,
                "name": it.get("name", ""),
                "price": it.get("price", 0),
                "on_hand": (it.get("stock") or {}).get("on_hand", 0),
                "reserved": (it.get("stock") or {}).get("reserved", 0),
                "status": it.get("status", "active"),
            })

        # сортировка/фильтры
        sort_by = (data or {}).get("sort_by") or "name"
        reverse = bool((data or {}).get("desc"))
        if sort_by == "name":
            items.sort(key=lambda x: (x["name"] or "").lower(), reverse=reverse)
        elif sort_by == "price":
            items.sort(key=lambda x: x["price"], reverse=reverse)
        elif sort_by == "on_hand":
            items.sort(key=lambda x: x["on_hand"], reverse=reverse)
        # фильтры можно добавить по (data.get("filters")), если появятся

        # Сохраняем порядок позиций для выбора по номеру
        list_id = str(uuid.uuid4())
        self._lists[list_id] = [i["sku"] for i in items]

        # Печать — по желанию (сейчас как в вашем сценарии)
        if (data or {}).get("print", True):
            print("\n№ | SKU       | Название                      | Цена | Налич.")
            print("--+-----------+-------------------------------+------+-------")
            for n, i in enumerate(items, 1):
                print(f"{n:>2} | {i['sku']:<9} | {i['name']:<29} | {i['price']:>4} | {i['on_hand']:>5}")
        
        return {"list_id": list_id, "items": items}
 
class PurchaseService: 
    """Пополнение склада""" 
    def handle(self, data): 
        action = data.get("action") 
        if action == "add_item": 
            if not current_user_is_admin():
                print("[PurchaseService] Доступ запрещён: требуется роль администратора.")
                log_action("PurchaseService", "add_item_denied", {"reason": "not_admin"})
                return
            name = str(data.get("name", "")).strip()
            price = data.get("price", None)
            on_hand = data.get("on_hand", None)

            # Валидация
            if not name:
                print("[PurchaseService] Некорректное имя товара (пусто).")
                return
            try:
                price = float(price)
            except Exception:
                print("[PurchaseService] Цена должна быть целым числом.")
                return
            try:
                on_hand = int(on_hand)
            except Exception:
                print("[PurchaseService] Количество (on_hand) должно быть целым числом.")
                return
            if price < 0 or on_hand < 0:
                print("[PurchaseService] Значения price и on_hand должны быть неотрицательными.")
                return

            db = load_inventory_db()
            idx = db.setdefault("indexes", {}).setdefault("by_name", {})
            if name in idx:
                print(f"[PurchaseService] Товар с названием '{name}' уже существует (sku {idx[name]}).")
                return

            item_obj = {
                "name": name,
                "price": price,
                "stock": {"on_hand": on_hand, "reserved": 0},
                "status": "active",
                "category": None,
                "attributes": {},
            }
            sku = inventory_upsert_item(db, sku=None, item_obj=item_obj)
            save_inventory_db(db)
            log_action("PurchaseService", "item_added", {"sku": sku, "name": name, "price": price, "on_hand": on_hand})
            print(f"[PurchaseService] Добавлен товар '{name}' (sku {sku}), цена {price}, на складе {on_hand}.")

            self.bus.publish("WarehouseUpdated", {"action": "warehosueUpdateNotify"})
            log_action("PurchaseService", "warehouse_updated_published", {"sku": sku, "name": name})