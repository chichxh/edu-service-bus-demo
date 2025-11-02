пользователь авторизуется -> сохраним во время сессии этого пользователя.  сессия закончится когда пользователь нажмет на 0

User:  - bus.send -> OrderCreated -> InventoryService() -> ProductOutOfStock -> NotificationService()
                                                      -> ProductInStock -> PaymentService() -->

--> PaymentSuccess -> InventoryService(reserveProduct()) -> ProductReserved -> DeliveryService() -> DeliveryScheduled -->
--> PaymentFailed -> NotificationService() 

--> NotificationService()

Admin:  - bus.send -> PurchaseCreated -> PurchaseService() -> WarehouseUpdated -> NotificationService() 
