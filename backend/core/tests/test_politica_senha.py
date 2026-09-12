"""Cobre a política de senha: os validadores em si e os três fluxos que a aplicam.

A tabela `CASOS_DE_PARIDADE` é o contrato com o cliente: os mesmos pares
(senha, veredito) aparecem em `frontend/src/lib/politicaSenha.test.js`. Se um caso
mudar de lado aqui e não lá, a tela passa a prometer o que o servidor recusa — que é
exatamente o defeito que motivou trocar a similaridade difusa por contenção.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework import serializers
from rest_framework.test import APITestCase

from core.serializers_auth import RegistrationSerializer
from core.validacao_senha import (
    TAMANHO_MAXIMO,
    TAMANHO_MINIMO,
    TermoDeContextoValidator,
    normalizar,
    termos_de_contexto,
)

User = get_user_model()

# (senha, aceita?, o que o caso prova) para o usuário `chrystian`/`chrystian@inscode.com.br`.
CASOS_DE_PARIDADE = [
    ("roda gigante de terca", True, "frase longa passa sem símbolo nenhum"),
    ("abacaxi-roxo", True, "o mínimo de 12 é inclusivo"),
    ("abacaxi-rox", False, "11 caracteres reprova"),
    ("Chrystian18!", False, "contém o nome de usuário, ainda que capitalizado"),
    ("Chrýstian18!", False, "acento não escapa da comparação"),
    ("chrystian-e-o-sol", False, "contém o local-part do e-mail"),
    ("freecash-rende-bem", False, "contém o nome do serviço"),
    ("123456789012345", False, "só dígitos reprova"),
]


class NormalizacaoTests(TestCase):
    """Garante a forma canônica usada na comparação de contexto."""

    def test_minusculas_e_sem_acento(self):
        """Maiúscula e acento não podem servir de escape."""
        self.assertEqual(normalizar("Chrýstian"), "chrystian")
        self.assertEqual(normalizar("JOÃO"), "joao")

    def test_vazio_e_none(self):
        """Campos opcionais em branco viram string vazia, sem estourar."""
        self.assertEqual(normalizar(""), "")
        self.assertEqual(normalizar(None), "")


class TermosDeContextoTests(TestCase):
    """Cobre a montagem da lista de termos proibidos."""

    def test_usuario_email_e_servico(self):
        """Usuário e local-part entram; o serviço entra sempre."""
        usuario = User(username="chrystian", email="contato@inscode.com.br")
        self.assertEqual(
            termos_de_contexto(usuario), ["freecash", "chrystian", "contato"]
        )

    def test_dominio_do_email_fica_de_fora(self):
        """Barrar «gmail» recusaria senha boa sem defender desta conta."""
        usuario = User(username="joana", email="joana@gmail.com")
        self.assertNotIn("gmail", termos_de_contexto(usuario))

    def test_termo_curto_e_descartado(self):
        """Um usuário «ana» barraria «planalto» — daí o piso de 4 caracteres."""
        usuario = User(username="ana", email="ana@exemplo.com")
        self.assertEqual(termos_de_contexto(usuario), ["freecash"])

    def test_sem_usuario_sobra_o_servico(self):
        """`validate_password` sem `user=` ainda protege o nome do serviço."""
        self.assertEqual(termos_de_contexto(None), ["freecash"])


class TermoDeContextoValidatorTests(TestCase):
    """Cobre o validador de contexto isolado dos demais."""

    def setUp(self):
        """Prepara o validador e um usuário de referência."""
        self.validador = TermoDeContextoValidator()
        self.usuario = User(username="chrystian", email="chrystian@inscode.com.br")

    def test_senha_com_o_usuario_e_recusada(self):
        """O caso que motivou a mudança: usuário inteiro + sufixo curto."""
        with self.assertRaises(DjangoValidationError) as ctx:
            self.validador.validate("Chrystian18!", user=self.usuario)
        self.assertEqual(ctx.exception.error_list[0].code, "password_contem_contexto")

    def test_senha_sem_contexto_passa(self):
        """Frase que não carrega nenhum termo não é assunto deste validador."""
        self.validador.validate("roda gigante de terca", user=self.usuario)


class PoliticaCompletaTests(TestCase):
    """Roda a cadeia inteira de `AUTH_PASSWORD_VALIDATORS`, como a aplicação roda."""

    def setUp(self):
        """Usuário de referência dos casos de paridade."""
        self.usuario = User(username="chrystian", email="chrystian@inscode.com.br")

    def _aceita(self, senha: str) -> bool:
        """Diz se a senha passa por todos os validadores configurados.

        Args:
            senha: Senha candidata.

        Returns:
            bool: `True` quando nenhum validador reclama.
        """
        try:
            validate_password(senha, user=self.usuario)
        except DjangoValidationError:
            return False
        return True

    def test_casos_de_paridade_com_o_cliente(self):
        """Cada caso da tabela compartilhada com o frontend."""
        for senha, aceita, motivo in CASOS_DE_PARIDADE:
            with self.subTest(senha=senha, motivo=motivo):
                self.assertEqual(self._aceita(senha), aceita, motivo)

    def test_sem_regra_de_composicao(self):
        """Nada de exigir maiúscula, dígito ou símbolo — é o ponto da rev. 4 do NIST."""
        self.assertTrue(self._aceita("cavalo bateria grampo"))

    def test_senha_comum_continua_recusada(self):
        """A lista de 20 mil senhas do Django segue valendo, mesmo com 12 caracteres."""
        self.assertFalse(self._aceita("startfinding"))

    def test_teto_de_tamanho(self):
        """O teto roda antes do hash: sem ele, o KDF trabalharia sobre o POST inteiro."""
        self.assertTrue(self._aceita("m" + "a" * (TAMANHO_MAXIMO - 1)))
        self.assertFalse(self._aceita("m" + "a" * TAMANHO_MAXIMO))

    def test_minimo_e_inclusivo(self):
        """`TAMANHO_MINIMO` caracteres bastam; um a menos, não."""
        base = "abacaxi-roxo"
        self.assertEqual(len(base), TAMANHO_MINIMO)
        self.assertTrue(self._aceita(base))
        self.assertFalse(self._aceita(base[:-1]))


class RegistroComPoliticaTests(APITestCase):
    """Prova que o registro aplica a política e devolve o erro no campo certo."""

    def _registrar(self, senha: str):
        """Valida um cadastro com a senha dada.

        Args:
            senha: Senha candidata.

        Returns:
            RegistrationSerializer: Serializer já validado ou com erros.
        """
        serializer = RegistrationSerializer(
            data={
                "username": "chrystian",
                "email": "chrystian@inscode.com.br",
                "password": senha,
                "confirm": senha,
            }
        )
        return serializer

    def test_senha_derivada_do_usuario_e_recusada_no_campo_password(self):
        """A recusa precisa chegar como erro de campo para a tela destacá-lo."""
        serializer = self._registrar("Chrystian18!")
        with self.assertRaises(serializers.ValidationError) as ctx:
            serializer.is_valid(raise_exception=True)
        self.assertIn("password", ctx.exception.detail)

    def test_frase_longa_e_aceita(self):
        """O caminho que a política quer incentivar."""
        self.assertTrue(self._registrar("roda gigante de terca").is_valid())
