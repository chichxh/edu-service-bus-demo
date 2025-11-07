import uuid
from utils import log_action,  load_users_db, load_inventory_db, save_inventory_db, save_users_db, load_session

class OrderService:
    """
    Сервис управления заказами
    - Создает заказ
    - Публикует событие 'order_created' для других сервисов
    """
    def handle(self, data):
        def gen_order_id() -> str:
            return f"ord_{uuid.uuid4().hex}" 
        def gen_payment_id() -> str:
            return f"pay_{uuid.uuid4().hex}"         

        action = data.get("action")
        if action != "createOrder":
            return None

        # ожидаем sku и qty от main.py
        sku = data.get("sku")
        qty = int(data.get("qty", 1))
        if not sku or qty <= 0:
            print("[OrderService] Некорректные данные заказа (sku/qty).")
            log_action("OrderService", "order_invalid_args", {"sku": sku, "qty": qty})
            return None

        inv = load_inventory_db()
        item = (inv.get("items") or {}).get(sku)
        if not item:
            print(f"[OrderService] Товар с SKU '{sku}' не найден.")
            log_action("OrderService", "order_sku_not_found", {"sku": sku})
            return None
        
        session = load_session() or {}
        user_id = session.get("user_id")

        order_payload = {
            "order_id": gen_order_id(),
            "payment_id": gen_payment_id(),
            "user_id": user_id,
            "item": {"sku": sku, "qty": qty, "name": item.get("name")},
        }

        # в будущем можно реализовать базу созданных заказов

        print(f"[OrderService] Создан заказ: {order_payload}")
        log_action("OrderService", "order_created", order_payload)
        self.bus.publish("orderCreated", {"action": "check_item", **order_payload})
        log_action("OrderService", "order_published", {"event": "orderCreated", "order_id": order_payload["order_id"]})
        return order_payload
        

class PaymentService:
    """
    Сервис обработки платежей.
    - Реагирует на событие 'PaymentRequested'.
    - Публикует событие 'payment_done' после успешной оплаты.
    - Публикует событие 'payment_failed' при неудачной оплате.
    """
    def __init__(self):
        self._processed_orders = set()  # идемпотентность по order_id

    def handle(self, data: dict):
        action = (data or {}).get("action")

        if action != "charge":
            return
        log_action("PaymentService", "payment_charge_requested", {"payload": data})

        order_id = data.get("order_id")
        user_id  = data.get("user_id")
        item     = (data.get("item") or {})  # {"sku","qty","name"}

        if not order_id or not user_id or not item:
            log_action("PaymentService", "invalid_payload", data)
            return

        # идемпотентность
        if order_id in self._processed_orders:
            self.bus.publish("PaymentSuccess", {
                "action": "schedule_delivery",
                "order_id": order_id,
                "user_id": user_id
            })
            log_action("PaymentService", "payment_idempotent_success", {"order_id": order_id})
            return

        inv = load_inventory_db()
        it = (inv.get("items") or {})
        if not it:
            self.bus.publish("PaymentFailed", {
                "action": "notify_payment_failed",
                "order_id": order_id,
                "reason": "sku_not_found"
            })
            log_action("PaymentService", "payment_failed_sku_not_found", {"order_id": order_id})
            # На всякий случай просим склад снять резерв
            self.bus.publish("ProductReserveRelease", {
                "action": "release_reservation",
                "order_id": order_id,
                "item": item
            })
            log_action("PaymentService", "release_reservation_published", {"order_id": order_id})
            return

        amount = data.get("amount")
        users = load_users_db()
        user  = (users.get("users") or {}).get(user_id)
        if not user:
            self.bus.publish("PaymentFailed", {
                "action": "notify_payment_failed",
                "order_id": order_id,
                "reason": "user_not_found"
            })
            log_action("PaymentService", "payment_failed_user_not_found", {"order_id": order_id, "user_id": user_id})
            self.bus.publish("ProductReserveRelease", {
                "action": "release_reservation",
                "order_id": order_id,
                "item": item
            })
            log_action("PaymentService", "release_reservation_published", {"order_id": order_id})
            return

        acc = user.get("account") or {}
        if acc.get("balance", 0) < amount:
            self.bus.publish("PaymentFailed", {
                "action": "notify_payment_failed",
                "order_id": order_id,
                "reason": "insufficient_funds",
                "required": amount,
                "balance": acc.get("balance", 0)
            })
            log_action("PaymentService", "payment_failed_insufficient_funds", {"order_id": order_id, "required": amount, "balance": acc.get("balance", 0)})
            self.bus.publish("ProductReserveRelease", {
                "action": "release_reservation",
                "order_id": order_id,
                "item": item
            })
            log_action("PaymentService", "release_reservation_published", {"order_id": order_id})
            return
        

        # списание
        acc["balance"] = acc.get("balance", 0) - amount
        user["account"] = acc
        save_users_db(users)

        log_action("PaymentService", "payment_charged", {
             "order_id": order_id,
             "amount": amount,
             "currency": acc.get("currency", "RUB")
         })

        # Зафиксировать резерв на складе (списать из on_hand и уменьшить reserved)
        # Выполняет InventoryService по событию ProductReserveCommit
        self.bus.publish("ProductReserveCommit", {
            "action": "commit_reservation",
            "order_id": order_id,
            "item": item  # ожидается {"sku": ..., "qty": ...}
        })
        log_action("PaymentService", "reserve_commit_published", {
            "order_id": order_id,
            "sku": (item or {}).get("sku"),
            "qty": (item or {}).get("qty")
        })



        log_action("PaymentService", "payment_charged", {
            "order_id": order_id,
            "amount": amount,
            "currency": acc.get("currency", "RUB")
        })
        self._processed_orders.add(order_id)

        self.bus.publish("PaymentSuccess", {
            "action": "schedule_delivery",
            "order_id": order_id,
            "user_id": user_id,
            "amount": amount,
            "currency": acc.get("currency", "RUB")
        })


class DeliveryService:
    """
    Сервис планирования доставок
    - Реагирует на событие PaymentSuccess
    - Публикует событие "DeliveryScheduled" 
    """
    def handle(self, data):
        action = data.get("action")
        if action == "schedule_delivery":
            order_id = data.get("order_id")
            user_id = data.get("user_id")
            amount = data.get("amount")
            currency = data.get("currency")

            ''' 
            Добавить БД для списка доставок
            добавить статус доставки? время? ответсвенного? и т.д.

            '''

            print(f"[DeliveryService] Доставка назначена для заказа '{order_id}' для пользвоателя '{user_id}' на сумму '{amount}' '{currency}' ")
            log_action("DeliveryService", "delivery_scheduled", {"order_id": order_id, "user_id": user_id, "amount": amount, "currency": currency})

            self.bus.publish("DeliveryScheduled", {"order_id": order_id, "user_id": user_id, "amount": amount, "currency": currency})
            log_action("DeliveryService", "delivery_published", {"event": "DeliveryScheduled", "order_id": order_id})
        
        if action == "close_delivery":
            pass

        if action == "reschedule_delivery":
            pass