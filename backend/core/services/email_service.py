"""Envio transacional de e-mails do sistema (verificação, reset de senha e avisos)."""

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
    """Normaliza o endereço de e-mail em minúsculas e sem espaços nas pontas."""
    return (email or "").strip().lower()


def _enviar_agora(mensagem: EmailMultiAlternatives, descricao: str) -> None:
    """Dispara a mensagem SMTP registrando em log sem propagar exceção."""
    try:
        mensagem.send(fail_silently=False)
        logger.info("E-mail enviado: %s", descricao)
    except Exception:
        logger.exception("Falha ao enviar e-mail: %s", descricao)


def enviar_email(assunto: str, template_base: str, contexto: dict, destinatario: str,
                 descricao: str) -> None:
    """Renderiza templates e agenda o envio via transaction.on_commit."""
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
        if settings.EMAIL_ASYNC:
            threading.Thread(
                target=_enviar_agora,
                args=(mensagem, descricao),
                daemon=False,
            ).start()
        else:
            _enviar_agora(mensagem, descricao)

    transaction.on_commit(despachar)


def _url_frontend(caminho: str) -> str:
    """Monta URL absoluta do SPA baseada em FRONTEND_BASE_URL."""
    return f"{settings.FRONTEND_BASE_URL}{caminho}"


def enviar_verificacao_email(user) -> None:
    """Envia o e-mail com link de confirmação de conta."""
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
    """Envia o e-mail com link de redefinição de senha."""
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
    """Envia link de confirmação para o novo endereço pendente do usuário."""
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
    """Notifica o endereço de e-mail anterior sobre a alteração realizada."""
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
