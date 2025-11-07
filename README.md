пользователь авторизуется -> сохраним во время сессии этого пользователя.  сессия закончится когда пользователь нажмет на 0

User:  - bus.send -> OrderCreated -> InventoryService() -> ProductOutOfStock -> NotificationService()
                                                        -> ProductInStock -> InventoryService(reserveProduct()) -> ProductReserved -> PaymentService() -->

--> PaymentSuccess ->  DeliveryService() -> DeliveryScheduled -> NotificationService()
--> PaymentFailed -> NotificationService() 


Admin:  - bus.send -> PurchaseCreated -> PurchaseService() -> WarehouseUpdated -> NotificationService() 


PaymentService должен сравнивать полученные данные от InventoryService и данные о счете пользователя. если на счете есть достаточное количество денег то списываем и присылаем уведомление и начинаем формировать доставку через DeliveryService. если денег нет то присылаем соотв уведомление. Уведомления реализованы через NotificationService, но пока через обычный print()