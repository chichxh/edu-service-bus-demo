class NotificationService:
    def handle(self, data):
        action = data.get("action")
        if action == "ProductOutOfStock":
            pass
        elif action == "PaymentFailed":
            pass
        elif action == "DeliveryScheduled":
            pass
        elif action == "WarehouseUpdated":
            pass