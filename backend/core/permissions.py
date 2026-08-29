"""Classes de permissão específicas do FreeCash."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import permissions


class EmailVerificadoOuCarencia(permissions.BasePermission):
    """Exige e-mail confirmado para importar dados, após um período de carência.

    Aplicada **apenas à importação**, e nunca ao CRUD financeiro nem à exportação.

    O critério é amplificação: importar recebe arquivo enviado pelo usuário e o
    processa com `pdfplumber` e leitores de planilha, gastando CPU e memória por
    requisição — é o que valeria a pena explorar a partir de uma conta descartável.
    Exportar percorre só os registros do próprio usuário, então uma conta
    descartável, sem dados, exporta nada: não há o que amplificar, e o portão foi
    retirado de lá.

    A carência existe para que o produto seja utilizável no primeiro acesso: quem
    acabou de se cadastrar trabalha imediatamente, e a exigência só aparece se a
    conta seguir não confirmada depois de alguns dias.
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

        Args:
            request (Request): Requisição em curso.
            view (APIView): View sendo acessada.

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

    Usa a flag `is_staff` do próprio `auth.User` em vez de introduzir um modelo de
    papéis. Para dois níveis — usuário e administrador — um modelo novo só
    adicionaria uma tabela a manter e um segundo lugar onde a autorização poderia
    divergir.

    O papel é sempre lido do banco, a cada requisição, e **nunca** de uma claim do
    JWT: com `ROTATE_REFRESH_TOKENS`, o SimpleJWT preserva o payload original na
    rotação, então um administrador rebaixado continuaria administrador por até
    sete dias. `is_active` é verificado explicitamente para que a suspensão de um
    administrador tenha efeito imediato.
    """

    message = "Esta área é restrita aos administradores da plataforma."

    def has_permission(self, request, view) -> bool:
        """Decide se a requisição parte de um administrador ativo.

        Args:
            request (Request): Requisição em curso.
            view (APIView): View sendo acessada.

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
