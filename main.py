from service_bus import ServiceBus 
from services.order_services import OrderService, PaymentService, DeliveryService # И другие, которые уже реализованы из предыдущей ЛР 
from services.inventory_services import InventoryService, PurchaseService 
from services.user_services import AuthService, VerificationService, ProfileService 
from services.notification_services import NotificationService 
from utils import log_action, load_json, save_json, clear_session 
 
def main(): 
    """ 
    Главный скрипт лабораторной работы. 
    Интерактивное меню позволяет: 
    - регистрировать пользователей 
    - добавлять/обновлять/удалять товары на складе 
    - создать заказ 
    """ 
    # -------------------------- 
    # Создание шины и сервисов 
    # -------------------------- 


    bus = ServiceBus() 

    bus.register_service("order", OrderService()) 
    bus.register_service("payment", PaymentService()) 
    bus.register_service("delivery", DeliveryService()) 
    bus.register_service("inventory", InventoryService()) 
    bus.register_service("purchase", PurchaseService()) 
    bus.register_service("auth", AuthService()) 
    bus.register_service("verify", VerificationService()) 
    bus.register_service("profile", ProfileService()) 
    bus.register_service("notify", NotificationService()) 
 

    bus.subscribe("registerAttemptCreated", "verify")
    bus.subscribe("emailVerificated", "profile")
    bus.subscribe("emailVerificationRequested", "notify", "on_email_verification_code")
    bus.subscribe("emailVerificationFail", "notify", "on_email_verification_fail")

    bus.subscribe("orderCreated", "inventory")
    bus.subscribe("ProductInStock", "inventory")
    bus.subscribe("PaymentRequested","payment")
    bus.subscribe("ProductOutOfStock", "notify", "on_product_out_of_stock")
    bus.subscribe("PaymentSuccess", "delivery")
    bus.subscribe("PaymentFailed", "notify", "on_payment_failed")
    bus.subscribe("DeliveryScheduled", "notify", "on_delivery_scheduled")

    bus.subscribe("ProductReserveRelease", "inventory")  # снять резерв при неуспешной оплате
    bus.subscribe("ProductReserveCommit", "inventory")   # зафиксировать резерв при успешной оплате

    bus.subscribe("PurchaseCreated", "purchase")
    bus.subscribe("WarehouseUpdated", "notify", "on_warehouse_updated")
    

    # -------------------------- 
    # Основное меню 
    # -------------------------- 
    while True: 
        print("\nВыберите действие:") 
        print("1. Зарегистрировать нового пользователя") 
        print("2. Войти в систему") 
        print("3. Управлять складом") 
        print("4. Создать заказ") 
        print("0. Выход") 
        choice = input("Введите номер действия: ").strip() 
 
        if choice == "1":        
            while True:
                print("\nВыберите роль:")
                print("1. Admin")
                print("2. User")
                choice = input("Введите номер действия: ").strip() 
                if choice == "1":
                    entered_role = "admin"
                    break 
                elif choice == "2":
                    entered_role = "user" 
                    break
                else:
                    print("Некорректный выбор, попробуйте снова.") 
                
            entered_email = input("\nВведите адрес эл. почты: ").strip() 
            entered_username = input("Придумайте имя пользователя: ").strip() 
            entered_password = input("Придумайте пароль: ").strip() 

            bus.send("auth", {"action": "register",
                "entered_email": entered_email, 
                "entered_username": entered_username, 
                "entered_password": entered_password, 
                "entered_role": entered_role })
 
        elif choice == "2": 
            entered_username = None
            entered_email = None

            while True:
                print("\nВыберите способ авторизации:")
                print("1. С логином")
                print("2. С эл. почтой")
                choice = input("Введите номер действия: ").strip() 
                if choice == "1":
                    entered_username = input("\nВведите имя пользователя: ").strip() 
                    break 
                elif choice == "2":
                    entered_email = input("\nВведите адрес эл. почты: ").strip() 
                    break
                else:
                    print("Некорректный выбор, попробуйте снова.") 
            
            entered_password = input("Введите пароль: ").strip() 
                
            bus.send("auth", {"action": "login",
                    "entered_email": entered_email, 
                    "entered_username": entered_username, 
                    "entered_password": entered_password })

 
        elif choice == "3": 
             while True:
                print("\nВыберите действие:")
                print("1. Посмотреть таблицу товаров")
                print("2. Добавить новый товар")
                print("3. Обратно")
                choice = input("Введите номер действия: ").strip() 
                if choice == "1":
                    bus.send("inventory", {"action": "list_items_full"})
                elif choice == "2":
                    name = input("Введите название нового товара: ").strip().lower()
                    price = float(input("Введите цену товара: "))
                    on_hand = int(input("Введите количество товара: "))
                    bus.send("purchase",
                             {"action": "add_item", 
                              "name": name, 
                              "price": price,
                              "on_hand": on_hand})
                elif choice == "3":
                    break
                else:
                    print("Некорректный выбор, попробуйте снова.") 
 
        elif choice == "4": 
            print("\nВыберите товар:")
            resp = bus.send("inventory", {"action": "list_items", "print": True, "sort_by": "name"})
            items = (resp or {}).get("items") or []
            if not items:
                print("Склад пуст.")
                item_choice = None
            else:
                # выбор по номеру
                while True:
                    raw = input("Выберите товар. Введите число: ").strip()
                    if raw.isdigit():
                        idx = int(raw)
                        if 1 <= idx <= len(items):
                            item_choice = items[idx - 1]   # <-- сохраняем выбор
                            break
                    print("Некорректный номер. Попробуйте ещё раз.")

                # передаём в сервис заказов СТАБИЛЬНЫЙ идентификатор — SKU
                sku = item_choice["sku"]
                qty_raw = input("Количество (по умолчанию 1): ").strip() or "1"
                try:
                    qty = max(1, int(qty_raw))
                except Exception:
                    qty = 1
                bus.send("order", {"action": "createOrder", "sku": sku, "qty": qty})


        elif choice == "0": 
            clear_session()
            print("Выход из системы...") 
            break 
 
        else: 
            print("Некорректный выбор, попробуйте снова.") 
 
if __name__ == "__main__": 
    main() 

 