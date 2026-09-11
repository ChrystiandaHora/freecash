"""Política de senha do FreeCash, aplicada aos três fluxos que definem senha.

Vale para o registro (`RegistrationSerializer`), a redefinição por link de e-mail
(`PasswordResetConfirmAPIView`) e a troca com o usuário autenticado
(`TrocaSenhaSerializer`) — os três chamam `validate_password`, então basta a lista de
`AUTH_PASSWORD_VALIDATORS` para que a regra seja a mesma nos três.

A política segue o NIST SP 800-63B rev. 4: o que sustenta a senha é **tamanho** e a
comparação contra listas, não regra de composição. Por isso não existe aqui exigência
de maiúscula, dígito ou símbolo — a literatura mostra que ela produz `Senha123!`, ganho
de entropia quase nulo com custo alto de usabilidade, e afasta justamente a frase longa
que seria mais forte.

O que substituiu a composição é a comparação contra termos de contexto: senha que
contém o nome de usuário, o local-part do e-mail ou o nome do serviço é recusada. Quem
ataca a conta já conhece esses termos, então `<usuário>+sufixo` é a primeira derivação
tentada — o segredo real é só o sufixo.

Por que **contenção** e não a similaridade difusa do `UserAttributeSimilarityValidator`
que estava aqui antes: a similaridade é uma razão do `SequenceMatcher` contra um limiar
de 0,7, um número que o cliente não consegue reproduzir. Sem reproduzir a regra não há
como desenhar um checklist honesto na tela, e a recusa só aparecia depois do POST. A
contenção é a mesma proteção escrita de um jeito que o frontend espelha caractere a
caractere — ver `frontend/src/lib/politicaSenha.js`, que é o espelho desta regra, e
`docs/autenticacao.md` para o histórico da decisão.
"""

import unicodedata

from django.contrib.auth.password_validation import MinimumLengthValidator
from django.core.exceptions import ValidationError

TAMANHO_MINIMO = 12

# Teto de tamanho, não de força: `validate_password` roda antes do hash, então sem ele
# um POST com alguns megabytes de senha viraria trabalho de KDF no servidor.
TAMANHO_MAXIMO = 128

# Termos curtos demais geram falso positivo: um usuário «ana» barraria «planalto».
TAMANHO_MINIMO_TERMO = 4

NOME_DO_SERVICO = "freecash"

ATRIBUTOS_DE_CONTEXTO = ("username", "first_name", "last_name")


def normalizar(texto: str) -> str:
    """Reduz um texto à forma usada na comparação: minúsculas e sem acento.

    Sem isso «Chrystian» passaria por conter o usuário «chrystian» e «Chrýstian»
    passaria pelas duas.

    Args:
        texto: Texto de origem, possivelmente vazio ou `None`.

    Returns:
        str: Texto em minúsculas, sem sinais diacríticos.
    """
    if not texto:
        return ""
    decomposto = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.casefold()


def termos_de_contexto(user=None) -> list[str]:
    """Monta os termos que a senha não pode conter, já normalizados.

    O e-mail entra pelo **local-part**: conter o endereço inteiro implica conter o
    local-part, então checar a parte antes do `@` cobre os dois casos. O domínio fica
    de fora de propósito — barrar «gmail» recusaria senhas boas sem defender de nada,
    já que o domínio não identifica esta conta.

    Args:
        user: Usuário (ou instância provisória, no registro). `None` deixa só os
            termos do próprio serviço.

    Returns:
        list[str]: Termos normalizados com pelo menos `TAMANHO_MINIMO_TERMO`
            caracteres, sem repetição e em ordem estável.
    """
    brutos = [NOME_DO_SERVICO]

    if user is not None:
        for atributo in ATRIBUTOS_DE_CONTEXTO:
            brutos.append(getattr(user, atributo, "") or "")

        email = getattr(user, "email", "") or ""
        brutos.append(email.split("@", 1)[0])

    termos = []
    for bruto in brutos:
        termo = normalizar(bruto)
        if len(termo) >= TAMANHO_MINIMO_TERMO and termo not in termos:
            termos.append(termo)
    return termos


class TamanhoSenhaValidator(MinimumLengthValidator):
    """Exige `TAMANHO_MINIMO` caracteres e recusa acima de `TAMANHO_MAXIMO`.

    Herda do validador do Django para reaproveitar a mensagem de mínimo já traduzida;
    o teto é acrescentado aqui porque o Django não tem validador equivalente.
    """

    def __init__(self, min_length: int = TAMANHO_MINIMO,
                 max_length: int = TAMANHO_MAXIMO):
        super().__init__(min_length=min_length)
        self.max_length = max_length

    def validate(self, password: str, user=None) -> None:
        """Valida o tamanho da senha nas duas pontas.

        Raises:
            ValidationError: Abaixo do mínimo ou acima do teto.
        """
        super().validate(password, user)
        if len(password) > self.max_length:
            raise ValidationError(
                f"A senha pode ter no máximo {self.max_length} caracteres.",
                code="password_too_long",
                params={"max_length": self.max_length},
            )

    def get_help_text(self) -> str:
        """Texto de ajuda exibido pelos formulários do Django admin."""
        return (
            f"Use de {self.min_length} a {self.max_length} caracteres. "
            "Uma frase que só você usa vale mais que símbolos no meio de uma palavra."
        )


class TermoDeContextoValidator:
    """Recusa senha que contenha usuário, e-mail ou o nome do serviço.

    Substitui o `UserAttributeSimilarityValidator`: mesma proteção, escrita como
    contenção em vez de similaridade difusa para que o cliente consiga espelhar a
    regra e avisar enquanto o usuário digita (ver o módulo).
    """

    def validate(self, password: str, user=None) -> None:
        """Procura cada termo de contexto dentro da senha.

        Raises:
            ValidationError: A senha contém um dos termos.
        """
        alvo = normalizar(password)
        for termo in termos_de_contexto(user):
            if termo in alvo:
                raise ValidationError(
                    "A senha não pode conter seu nome de usuário, seu e-mail nem "
                    "o nome do serviço.",
                    code="password_contem_contexto",
                    params={"termo": termo},
                )

    def get_help_text(self) -> str:
        """Texto de ajuda exibido pelos formulários do Django admin."""
        return (
            "A senha não pode conter seu nome de usuário, seu e-mail nem o nome "
            "do serviço."
        )
