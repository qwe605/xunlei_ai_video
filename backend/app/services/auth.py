import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import Settings, get_settings
from app.database.models import AuthSessionRecord, UserRecord
from app.database.repositories import AuthRepository
from app.database.session import session_scope
from app.schemas import AuthCredentials, RegisterRequest, UserRead


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class AuthResult:
    user: UserRead
    token: str


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _password_hash(password: str, salt: bytes) -> str:
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return base64.b64encode(derived).decode("ascii")


class AuthService:
    """注册、登录和服务端会话校验；不向前端暴露密码或令牌哈希。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def register(self, payload: RegisterRequest) -> AuthResult:
        email = payload.email.strip().lower()
        display_name = payload.display_name.strip()
        if len(display_name) < 2:
            raise AuthError(422, "昵称至少需要 2 个字符")
        with session_scope() as session:
            repository = AuthRepository(session)
            if repository.get_user_by_email(email) is not None:
                raise AuthError(409, "该邮箱已注册")
            is_first_user = repository.count_users() == 0
            salt = secrets.token_bytes(16)
            user = repository.create_user(
                UserRecord(
                    id=uuid.uuid4().hex,
                    email=email,
                    display_name=display_name,
                    password_salt=base64.b64encode(salt).decode("ascii"),
                    password_hash=_password_hash(payload.password, salt),
                )
            )
            if is_first_user:
                repository.adopt_legacy_owner(user.id)
            token = self._create_session(repository, user.id)
            return AuthResult(self._to_schema(user), token)

    def login(self, payload: AuthCredentials) -> AuthResult:
        email = payload.email.strip().lower()
        with session_scope() as session:
            repository = AuthRepository(session)
            user = repository.get_user_by_email(email)
            if user is None:
                raise AuthError(401, "邮箱或密码不正确")
            salt = base64.b64decode(user.password_salt)
            candidate = _password_hash(payload.password, salt)
            if not hmac.compare_digest(candidate, user.password_hash):
                raise AuthError(401, "邮箱或密码不正确")
            token = self._create_session(repository, user.id)
            return AuthResult(self._to_schema(user), token)

    def authenticate(self, token: str | None) -> UserRead | None:
        if not token:
            return None
        with session_scope() as session:
            user = AuthRepository(session).get_session_user(_token_hash(token))
            return self._to_schema(user) if user else None

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with session_scope() as session:
            AuthRepository(session).delete_session(_token_hash(token))

    def _create_session(self, repository: AuthRepository, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        repository.create_session(
            AuthSessionRecord(
                id=uuid.uuid4().hex,
                user_id=user_id,
                token_hash=_token_hash(token),
                expires_at=datetime.now(timezone.utc)
                + timedelta(days=self._settings.auth_session_days),
            )
        )
        return token

    @staticmethod
    def _to_schema(user: UserRecord) -> UserRead:
        return UserRead(id=user.id, email=user.email, display_name=user.display_name)
