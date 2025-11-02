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
    bus.subscribe("emailVerificationFail", "notify")

    bus.subscribe("orderCreated", "inventory")
    bus.subscribe("ProductInStock", "payment")
    bus.subscribe("ProductOutOfStock", "notify")
    bus.subscribe("PaymentSuccess", "inventory")
    bus.subscribe("PaymentFailed", "notify")
    bus.subscribe("ProductReserved", "delivery")
    bus.subscribe("DeliveryScheduled", "notify")

    bus.subscribe("PurchaseCreated", "purchase")
    bus.subscribe("WarehouseUpdated", "notify")
    

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
                    entered_role = "Admin"
                    break 
                elif choice == "2":
                    entered_role = "User" 
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
                    "entered_password": entered_password, 
                    "entered_role": entered_role })

 
        elif choice == "3": 
            # TODO: Вызвать PurchaseService для управления складом 
            # - проверить права пользователя (только admin) 
            pass 
 
        elif choice == "4": 
            # TODO: Вызвать OrderService для создания нового заказа 
            # - проверить наличие товара через InventoryService 
            pass 


 
        elif choice == "0": 
            clear_session()
            print("Выход из системы...") 
            break 
 
        else: 
            print("Некорректный выбор, попробуйте снова.") 
 
if __name__ == "__main__": 
    main() 

 