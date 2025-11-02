пользователь авторизуется -> сохраним во время сессии этого пользователя.  сессия закончится когда пользователь нажмет на 0

User:  - bus.send -> OrderCreated -> InventoryService() -> ProductOutOfStock -> NotificationService()
                                                      -> ProductInStock -> PaymentService() -->

--> PaymentSuccess -> InventoryService(reserveProduct()) -> ProductReserved -> DeliveryService() -> DeliveryScheduled -->
--> PaymentFailed -> NotificationService() 

--> NotificationService()

Admin:  - bus.send -> PurchaseCreated -> PurchaseService() -> WarehouseUpdated -> NotificationService() 


Auth:

----------
from utils import get_current_user, current_user_is_admin, load_session

uid, user = get_current_user()   # uid либо None, user либо None
if current_user_is_admin():
    print("Можно пополнять склад")
else:
    print("Доступ только для admin")