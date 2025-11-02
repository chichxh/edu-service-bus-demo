import json
from utils import log_action,  load_users_db, load_inventory_db, save_inventory_db, save_users_db

class OrderService:
    """
    Сервис управления заказами
    - Создает заказ
    - Публикует событие 'order_created' для других сервисов
    """
    def handle(self, data):
        print(f"[OrderService] Создан заказ: {data}")
        # Публикуем событие, чтобы PaymentService узнал о заказе
        self.bus.publish("order_created", {
            "order_id": data.get("order_id"),
            "user_id": data.get("user_id"),
            "amount": data.get("amount"),
            "item": data.get("item")
            })
        

class PaymentService:
    """
    Сервис обработки платежей.
    - Реагирует на событие 'order_created'.
    - Публикует событие 'payment_done' после успешной оплаты.
    - Публикует событие 'payment_failed' при неудачной оплате.
    """
    def handle(self, data):
        print(f"[PaymentService] Обработка платежа для заказа {data.get('order_id')} " 
            f"на сумму {data.get('amount')}")
        
        users_db = load_users_db()
        user_id = data.get("user_id")
        amount = data.get("amount", 0)

        account = users_db.get("accounts", {}).get(user_id)
        if not account:
            print(f"[PaymentService] Ошибка: счет пользователя {user_id} не найден.")
            payment_successful = False
        elif amount > account["balance"]:
            print(f"[PaymentService] Недостаточно средств: баланс {account['balance']}, сумма {amount}")
            payment_successful = False
        else:
            account["balance"] -= amount
            payment_successful = True
            print(f"[PaymentService] Списание {amount}. Новый баланс: {account['balance']}")

        # сохраняем изменения
        save_users_db() #доделать

        if payment_successful:
            self.bus.publish("payment_done", data)
        else:
            self.bus.publish("payment_failed", data)


class DeliveryService:
    """
    Сервис планирования доставок
    - Реагирует на событие ProductReserved
    - Публикует событие "DeliveryScheduled" 

    #TODO: В будущем добавить проверку доступных слотов для доставки
           Публиковать событие "DeliveryScheduleFailed"
    """
    def hande(self, data):
        action = data.get("action")
        if action == "delivery":
            pass