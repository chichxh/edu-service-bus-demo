from utils import log_action, load_inventory_db, save_inventory_db, inventory_upsert_item, current_user_is_admin
 
class InventoryService: 
    """Управление складом""" 
    def handle(self, data): 
        action = data.get("action") 
        if action == "check_item": 
            # TODO: Проверить наличие товара на складе 
            pass 
        elif action == "reserve_item": 
            # TODO: Зарезервировать товар для заказа 
            pass 
        elif action == "list_items":
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
                print(f"{sku:<9} | {name:<24} | {price:>5} | {on_hand:>9} | {reserved:>6}")
 
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