"""Classes de permissão específicas do FreeCash."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import permissions


class EmailVerificadoOuCarencia(permissions.BasePermission):
    """Exige e-mail confirmado para importar dados, após um período de carência.

    Aplicada **apenas à importação**, nunca ao CRUD financeiro nem à exportação. O
    critério é amplificação: importar processa arquivo enviado com `pdfplumber` e
    leitores de planilha, gastando CPU e memória por requisição — é o que valeria
    explorar a partir de uma conta descartável. Exportar percorre só os registros do
    próprio usuário, e uma conta descartável não tem dados.

    A carência mantém o produto utilizável no primeiro acesso: a exigência só aparece se
    a conta seguir não confirmada depois de alguns dias.
    """

    message = (
        "Confirme seu endereço de e-mail para importar dados. Reenvie a confirmação "
        "a partir do aviso no topo da tela."
    )

    MENSAGEM_SEM_EMAIL = (
        "Cadastre um endereço de e-mail em Minha Conta para importar dados. "
        "Ele também é o que permite recuperar sua senha."
    )

    def has_permission(self, request, view) -> bool:
        """Decide se a requisição pode prosseguir.

        Returns:
            bool: True se o e-mail está confirmado ou a conta ainda está na carência.
        """
        usuario = request.user
        if not usuario or not usuario.is_authenticated:
            return False

        config = getattr(usuario, "config", None)
        if config is not None and config.email_verificado:
            return True

        # Conta sem endereço nenhum: pedir para "confirmar o e-mail" seria um beco
        # sem saída, porque não há e-mail a confirmar e o reenvio recusa a operação.
        # É a situação das contas criadas antes de o endereço virar obrigatório —
        # que não são contas descartáveis, e portanto não são o alvo deste portão.
        # A mensagem aponta para onde a pessoa resolve isso de fato.
        if not usuario.email:
            self.message = self.MENSAGEM_SEM_EMAIL

        limite = usuario.date_joined + timedelta(
            days=settings.EMAIL_VERIFICATION_GRACE_DAYS
        )
        return timezone.now() <= limite


class IsAdminPlataforma(permissions.BasePermission):
    """Restringe o acesso aos administradores da plataforma.

    Usa `is_staff` do próprio `auth.User` em vez de um modelo de papéis: para dois
    níveis, um modelo novo só somaria uma tabela a manter e um segundo lugar onde a
    autorização poderia divergir.

    O papel é lido do banco a cada requisição, nunca de claim do JWT — com
    `ROTATE_REFRESH_TOKENS` o payload sobrevive à rotação, e um administrador rebaixado
    seguiria administrador por sete dias. `is_active` é checado à parte para a suspensão
    ter efeito imediato.
    """

    message = "Esta área é restrita aos administradores da plataforma."

    def has_permission(self, request, view) -> bool:
        """Decide se a requisição parte de um administrador ativo.

        Returns:
            bool: True apenas para usuário autenticado, ativo e com `is_staff`.
        """
        usuario = request.user
        return bool(
            usuario
            and usuario.is_authenticated
            and usuario.is_active
            and usuario.is_staff
        )
