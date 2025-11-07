class ServiceBus:
    """
    Атрибуты:
    - services: словарь зарегистрированных сервисов {name: service_instance}
    - subscribers: словарь подписок на события {event_name: [service_name1,
    service_name2]}
    """
    def __init__(self):
        self.services = {}
        self.subscribers = {}

    def register_service(self, name, service):
        """
        Регистрирует сервис в шине и передает ссылку на шину сервису.
        """
        self.services[name] = service
        service.bus = self # сервис может публиковать события через шину

    def subscribe(self, event_name, service_name, handler_method=None):
        """
        Подписывает сервис на событие.
        handler_method - опциональный метод для обработки конкретного события
        """
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []
        self.subscribers[event_name].append({
            'service': service_name,
            'handler': handler_method
        })

    def publish(self, event_name, data):
        """
        Публикует событие: уведомляет все подписанные сервисы.
        """
        print(f"\n[ServiceBus] Событие '{event_name}' опубликовано с данными: {data}")
        if event_name in self.subscribers:
            for subscription in self.subscribers[event_name]:
                service_name = subscription['service']
                handler_method = subscription.get('handler')
                self.send(service_name, data, handler_method)

    def send(self, target_service, data, handler_method=None):
        """
        Отправляет данные конкретному сервису (вызывает handle или специфический обработчик).
        """
        if target_service not in self.services:
            print(f"[ServiceBus] Ошибка: сервис '{target_service}' не найден.")
            return
        
        service = self.services[target_service]
        if handler_method and hasattr(service, handler_method):
            # Вызываем специфический обработчик события
            return getattr(service, handler_method)(data)
        else:
            # Вызываем стандартный обработчик
            return service.handle(data)