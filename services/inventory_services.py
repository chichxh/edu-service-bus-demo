from utils import log_action, load_json, save_json 
 
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
 
class PurchaseService: 
    """Пополнение склада""" 
    def handle(self, data): 
        action = data.get("action") 
        if action == "add_item": 
            # TODO: Добавить новый товар на склад 
            # - проверка прав пользователя (только админ) 
            pass 