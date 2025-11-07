from utils import log_action

class NotificationService:
    """
    Читабельные уведомления для пользователя.
    ВНИМАНИЕ: этот сервис подписывается на конкретные события
    через именованные handler'ы (см. main.py -> bus.subscribe(..., handler)).
    """
    # --- Фоллбек, если вдруг подписались без handler'а
    def handle(self, data: dict):
        action = (data or {}).get("action") or "event"
        self._print(f"Получено событие: {action}")

    # --- Handlers, привязанные к событиям шины ---
    def on_product_out_of_stock(self, data: dict):
        sku = data.get("sku")
        qty = data.get("qty")
        order_id = data.get("order_id")
        log_action("NotificationService", "product_out_of_stock", {"sku": sku, "qty": qty, "order_id": order_id})
        if order_id:
            self._print(
                f"Товар закончился: sku={sku}, запрошено={qty}. "
                f"Заказ {order_id} не может быть выполнен."
            )
        else:
            self._print(f"Товар закончился: sku={sku}, запрошено={qty}.")

    def on_payment_failed(self, data: dict):
        order_id = data.get("order_id")
        reason = data.get("reason")
        log_action("NotificationService", "payment_failed_notice", data)
        if reason == "sku_not_found":
            msg = "товар не найден на складе"
        elif reason == "user_not_found":
            msg = "пользователь не найден"
        elif reason == "insufficient_funds":
            required = data.get("required")
            balance = data.get("balance")
            if balance is not None:
                msg = f"недостаточно средств (нужно: {required}, доступно: {balance})"
            else:
                msg = f"недостаточно средств (нужно: {required})"
        else:
            msg = f"причина: {reason}"
        if order_id:
            self._print(f"Оплата заказа {order_id} не прошла: {msg}.")
        else:
            self._print(f"Оплата не прошла: {msg}.")

    def on_delivery_scheduled(self, data: dict):
        order_id = data.get("order_id")
        user_id = data.get("user_id")
        amount = data.get("amount")
        currency = data.get("currency")
        log_action("NotificationService", "delivery_scheduled_notice", {"order_id": order_id, "user_id": user_id, "amount": amount, "currency": currency})
        self._print(
            f"Доставка назначена: заказ {order_id}, пользователь {user_id}, "
            f"сумма {amount} {currency}."
        )

    def on_warehouse_updated(self, data: dict):
        log_action("NotificationService", "warehouse_updated_notice", {"payload": data})
        self._print("Склад обновлён: приход товаров зарегистрирован.")

    def on_email_verification_fail(self, data: dict):
        user = (data or {}).get("user_obj") or {}
        email = user.get("email")
        username = user.get("username") or ""
        who = f"{username} <{email}>" if email else (username or "пользователь")
        log_action("NotificationService", "email_verification_fail_notice", {"user": {"username": username, "email": email}})
        self._print(f"Подтверждение email не пройдено для {who}.")

    def on_email_verification_code(self, data: dict):
        """Отправка кода верификации пользователю (эмуляция email-уведомления)."""
        user = (data or {}).get("user_obj") or {}
        code = (data or {}).get("code")
        email = user.get("email")
        username = user.get("username") or ""
        who = f"{username} <{email}>" if email else (username or "пользователь")
        log_action("NotificationService", "email_verification_code_sent",
                {"user": {"username": username, "email": email}, "code": code})
        print(f"[Notification] Отправлен код подтверждения {code} для {who}. Введите этот код верификации.")


    # --- helpers ---
    def _print(self, message: str):
        print(f"[Notification] {message}")