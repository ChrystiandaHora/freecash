"""Classes de limitação de taxa (throttling) dos endpoints de autenticação.

Antes destas classes, `POST /api/token/` e `POST /api/register/` aceitavam
tentativas ilimitadas — força bruta de senha sem qualquer atrito, e criação de
contas em massa. O throttling é aplicado explicitamente por view (opt-in), e não
globalmente, para não estrangular o uso normal do aplicativo.

Todas as classes usam o alias de cache "throttle" (DatabaseCache), compartilhado
entre os workers do gunicorn. Com o LocMemCache padrão, cada worker manteria a sua
própria contagem e o limite efetivo seria multiplicado pelo número de processos.
"""

from django.core.cache import caches
from rest_framework.throttling import ScopedRateThrottle


class AuthScopedRateThrottle(ScopedRateThrottle):
    """Throttle por escopo que usa o cache compartilhado entre workers.

    A view define `throttle_scope`, e a taxa correspondente vem de
    `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`.
    """

    cache = caches["throttle"]


class PasswordResetEmailThrottle(AuthScopedRateThrottle):
    """Limita pedidos de redefinição de senha por endereço de e-mail alvo.

    O limite por IP, isolado, não impede que um atacante distribuído use o sistema
    como canhão de spam contra um endereço específico. Esta classe fecha essa via
    contando as tentativas pelo e-mail solicitado, e não por quem solicitou.

    O e-mail é normalizado e reduzido a um hash antes de compor a chave de cache,
    para que endereços de usuários não fiquem legíveis na tabela de cache.
    """

    scope = "senha_reset_email"

    def get_cache_key(self, request, view):
        """Compõe a chave de cache a partir do e-mail alvo da requisição.

        Returns:
            str | None: Chave de cache, ou None quando não há e-mail no corpo — nesse
                caso o throttle por IP já cobre a requisição.
        """
        import hashlib

        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return None

        digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:32]
        return f"throttle_{self.scope}_{digest}"
