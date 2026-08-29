"""Envio de e-mails transacionais do FreeCash.

Este módulo concentra dois assuntos que costumam vazar para dentro das views: como
o e-mail sai (síncrono ou em thread, e o que fazer quando falha) e como o link
enviado é montado.

Duas decisões estruturais:

**O envio acontece fora da transação.** Toda chamada é agendada com
`transaction.on_commit`. Sem isso, um erro posterior no `atomic` desfaria a criação
do usuário e ele receberia, ainda assim, um e-mail confirmando uma conta que não
existe — com um link que nunca funcionaria.

**A falha de envio nunca derruba a requisição.** Se o SMTP estiver fora do ar, o
cadastro do usuário não deve falhar: a conta foi criada, e todo fluxo aqui oferece
"reenviar" como recuperação. A falha vai para o log, não para o cliente.

O link aponta sempre para o SPA, nunca para a API. Clientes de e-mail e
antivírus corporativos pré-carregam URLs das mensagens; se o link fosse o endpoint
de confirmação, o token seria consumido antes de o usuário clicar.
"""

import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.services.tokens import email_change_token, email_verification_token

logger = logging.getLogger("core")


def normalizar_email(email: str) -> str:
    """Reduz um endereço à forma canônica usada no banco.

    Toda escrita de e-mail no sistema passa por esta função, para que o índice
    único sobre `LOWER(email)` e as buscas por `email__iexact` concordem sempre.

    Args:
        email (str): Endereço informado pelo usuário.

    Returns:
        str: Endereço sem espaços nas bordas e em minúsculas.
    """
    return (email or "").strip().lower()


def _enviar_agora(mensagem: EmailMultiAlternatives, descricao: str) -> None:
    """Entrega a mensagem, registrando falhas sem propagá-las.

    Args:
        mensagem (EmailMultiAlternatives): Mensagem pronta para envio.
        descricao (str): Rótulo do fluxo, usado no log.
    """
    try:
        mensagem.send(fail_silently=False)
        logger.info("E-mail enviado: %s", descricao)
    except Exception:
        # Deliberadamente amplo: qualquer falha de rede, autenticação ou
        # configuração do provedor não pode transformar-se em erro para o usuário.
        logger.exception("Falha ao enviar e-mail: %s", descricao)


def enviar_email(assunto: str, template_base: str, contexto: dict, destinatario: str,
                 descricao: str) -> None:
    """Monta e agenda o envio de um e-mail em texto e HTML.

    Args:
        assunto (str): Assunto da mensagem.
        template_base (str): Caminho do template sem extensão, relativo a `emails/`.
            Espera encontrar as versões `.txt` e `.html`.
        contexto (dict): Contexto de renderização dos templates.
        destinatario (str): Endereço de destino.
        descricao (str): Rótulo do fluxo, usado no log.
    """
    if not destinatario:
        logger.warning("Envio ignorado, destinatário vazio: %s", descricao)
        return

    corpo_texto = render_to_string(f"emails/{template_base}.txt", contexto)
    corpo_html = render_to_string(f"emails/{template_base}.html", contexto)

    mensagem = EmailMultiAlternatives(
        subject=assunto,
        body=corpo_texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
    )
    mensagem.attach_alternative(corpo_html, "text/html")

    def despachar():
        """Envia agora ou em thread, conforme a configuração do ambiente."""
        if settings.EMAIL_ASYNC:
            # daemon=False para que o processo não seja reciclado no meio do envio.
            threading.Thread(
                target=_enviar_agora,
                args=(mensagem, descricao),
                daemon=False,
            ).start()
        else:
            _enviar_agora(mensagem, descricao)

    # Só envia depois que a transação em curso for confirmada. Fora de uma
    # transação, o Django executa o callback imediatamente.
    transaction.on_commit(despachar)


def _url_frontend(caminho: str) -> str:
    """Compõe uma URL absoluta do SPA.

    Args:
        caminho (str): Caminho relativo, começando com barra.

    Returns:
        str: URL absoluta baseada em `FRONTEND_BASE_URL`.
    """
    return f"{settings.FRONTEND_BASE_URL}{caminho}"


def enviar_verificacao_email(user) -> None:
    """Envia o link de confirmação de endereço de e-mail.

    Args:
        user (User): Usuário destinatário, com `email` já definido.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)

    contexto = {
        "nome": user.get_username(),
        "link": _url_frontend(f"/verificar-email/{uid}/{token}"),
        "validade_dias": max(1, settings.EMAIL_VERIFICATION_TIMEOUT // 86400),
    }
    enviar_email(
        assunto="Confirme seu e-mail no FreeCash",
        template_base="verificacao",
        contexto=contexto,
        destinatario=user.email,
        descricao=f"verificacao de e-mail (usuario {user.pk})",
    )


def enviar_reset_senha(user, token: str) -> None:
    """Envia o link de redefinição de senha.

    O token é recebido pronto, e não gerado aqui, porque quem decide se o pedido
    resulta em envio é a view — que precisa responder de forma idêntica exista ou
    não uma conta com aquele endereço.

    Args:
        user (User): Usuário destinatário.
        token (str): Token de redefinição já gerado.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    contexto = {
        "nome": user.get_username(),
        "link": _url_frontend(f"/redefinir-senha/{uid}/{token}"),
        "validade_horas": max(1, settings.PASSWORD_RESET_TIMEOUT // 3600),
    }
    enviar_email(
        assunto="Redefinição de senha do FreeCash",
        template_base="reset_senha",
        contexto=contexto,
        destinatario=user.email,
        descricao=f"reset de senha (usuario {user.pk})",
    )


def enviar_confirmacao_troca_email(user) -> None:
    """Envia o link de confirmação para o **novo** endereço de uma troca.

    O destino é `config.email_pendente`, e não `user.email`: o que precisa ser
    provado é a posse do endereço novo. Enviar para o atual não provaria nada — o
    usuário já tem acesso a ele.

    Args:
        user (User): Usuário que solicitou a troca, com `email_pendente` definido.
    """
    config = getattr(user, "config", None)
    pendente = getattr(config, "email_pendente", "") if config else ""
    if not pendente:
        logger.warning(
            "Troca de e-mail sem endereço pendente (usuário %s).", user.pk
        )
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_change_token.make_token(user)

    contexto = {
        "nome": user.get_username(),
        "email_novo": pendente,
        "link": _url_frontend(f"/conta/confirmar-email/{uid}/{token}"),
        "validade_dias": max(1, settings.EMAIL_VERIFICATION_TIMEOUT // 86400),
    }
    enviar_email(
        assunto="Confirme seu novo e-mail no FreeCash",
        template_base="troca_email",
        contexto=contexto,
        destinatario=pendente,
        descricao=f"troca de e-mail (usuario {user.pk})",
    )


def avisar_troca_de_email(user, email_anterior: str) -> None:
    """Avisa o endereço **antigo** de que o e-mail da conta foi alterado.

    É a rede de segurança do fluxo: se a troca não partiu do dono, este é o aviso
    que chega a ele enquanto ainda tem como reagir. Por isso vai para o endereço
    que está sendo desativado, e não para o novo.

    Args:
        user (User): Usuário cuja conta mudou de endereço.
        email_anterior (str): Endereço que deixou de valer.
    """
    if not email_anterior:
        return

    contexto = {
        "nome": user.get_username(),
        "email_novo": user.email,
        "link_suporte": _url_frontend("/esqueci-senha"),
    }
    enviar_email(
        assunto="O e-mail da sua conta FreeCash foi alterado",
        template_base="aviso_troca_email",
        contexto=contexto,
        destinatario=email_anterior,
        descricao=f"aviso de troca de e-mail (usuario {user.pk})",
    )
