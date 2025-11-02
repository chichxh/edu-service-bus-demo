from utils import log_action, load_users_db, save_users_db, users_upsert, save_session

class AuthService:
    def handle(self, data):
        action = (data or {}).get("action")
        if action == "register":
            return self._register(data)
        elif action == "login":
            return self._login(data)
        else:
            log_action("AuthService", f"unknown_action: {action!r}", data or {})
            print("[AuthService] Неизвестное действие.")
        return None

    def _register(self, data: dict):
        entered_username = (data.get("entered_username") or "").strip()
        entered_email = (data.get("entered_email") or "").strip()
        entered_password = (data.get("entered_password") or "").strip()
        role = (data.get("entered_role") or "user").strip() or "user"

        log_action("AuthService", "register_attempt", {"entered_username": entered_username, 
                                                       "entered_email": entered_email, 
                                                       "entered_password":entered_password, 
                                                       "role": role})

        db = load_users_db()
        if not entered_username or not entered_password:
            log_action("AuthService", "user_register_failed", {"username": entered_username, "reason": "No username or email"})
            print("Имя пользователя и пароль обязательны.")
            return None
        if entered_username in db.get("indexes", {}).get("by_username", {}):
            log_action("AuthService", "user_register_failed", {"username": entered_username, "reason": "Username already taken"})
            print("Пользователь с таким именем уже существует")
            return None
        if entered_email and entered_email in db.get("indexes", {}).get("by_email", {}):
            log_action("AuthService", "user_register_failed", {"username": entered_email, "reason": "Email already registered"})
            print("Пользователь с таким email уже существует")
            return None

        user_obj = {
            "username": entered_username,
            "email": entered_email,
            "role": role,
            "password_hash": entered_password,
            "status": "active",
            "account": {
                "balance": 0,
                "currency": "RUB"
            },
        }

        self.bus.publish("registerAttemptCreated", {"action": "verify_email", "user_obj": user_obj})
        

    def _login(self, data: dict):
        entered_username = (data.get("entered_username") or "").strip()
        entered_email = (data.get("entered_email") or "").strip()
        entered_password = (data.get("entered_password") or "").strip()

        db = load_users_db()
        idx = db.get("indexes", {})
        users = db.get("users", {})
        uid = idx.get("by_username", {}).get(entered_username) or idx.get("by_email", {}).get(entered_email)
        if not uid or uid not in users:
            print("[AuthService] Пользователь не найден.")
            return None

        user_obj = users[uid]
        if user_obj.get("password_hash") != entered_password:
            print("[AuthService] Неверный пароль.")
            log_action("AuthService", "login_failed_wrong_password",
                {"username": entered_username or entered_email})
            return None

        save_session(uid, user_obj, source="login")
        log_action("AuthService", "login_success", {"user_id": uid, "username": user_obj.get("username")})
        print(f"[AuthService] Добро пожаловать, {user_obj.get('username')}!")
        try: self.bus.publish("user_authenticated", {"user_id": uid, "username": user_obj.get("username"), "role": user_obj.get("role")})
        except Exception: pass
        return {"user_id": uid, "username": user_obj.get("username"), "role": user_obj.get("role")}


class VerificationService: 
    """Подтверждение почты и проверка данных""" 
    def handle(self, data): 
        action = data.get("action") 
        if action == "verify_email": 
            user_obj = data.get("user_obj")
            print("Is this your email?", user_obj["email"])
            choise = input("[Y] - Yes, [N] - No: ").strip()
            if choise == "Y" or "y":
                self.bus.publish("emailVerificated", {"action": "create_profile", "user_obj": user_obj})
            elif choise == "N" or "n":
                self.bus.publish("emailVerificationFail", {action: "notifyEmailVerificationFail", user_obj: user_obj})

 
class ProfileService: 
    """Создание и обновление профиля пользователя""" 
    def handle(self, data): 
        action = data.get("action") 
        if action == "create_profile": 
            db = load_users_db()

            user_obj=data.get("user_obj")
            username = user_obj.get("username")
            role = user_obj.get("role")
            uid = users_upsert(db, uid=None, user_obj=user_obj)

            save_session(uid, user_obj, source="register")
            save_users_db(db)

            log_action("AuthService", "user_registered", {"user_id": uid, "username": username})
            print(f"[AuthService] Регистрация успешна. Пользователь '{username}' вошёл в систему.")

            self.bus.publish("user_authenticated", {"user_id": uid, "username": username, "role": role})


        

