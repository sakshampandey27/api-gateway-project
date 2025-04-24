import jwt
import datetime

SECRET_KEY = "jobs2025"

payload = {
    "sub": "test_user",
    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
}

token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
print(token)
