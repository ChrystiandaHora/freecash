"""Testes de compatibilidade da restauração com backups de versões anteriores.

As chaves do arquivo `.fcbk` são **nomes de classe de modelo**
(`data[app][NomeDoModelo]`) e **nomes de campo** (chaves estrangeiras como
`<campo>_uuid`). Isso torna qualquer renomeação no código uma quebra de formato de
arquivo: um `.fcbk` gerado antes da mudança continua trazendo os nomes antigos.

O modo de falha é o pior possível num backup — a restauração não dá erro, apenas
não encontra os registros e devolve a base sem eles. Estes testes existem para que
a próxima renomeação de modelo ou de campo não passe sem o mapa de compatibilidade
correspondente.

Caso concreto coberto: `ReceitaRecorrente` virou `LancamentoRecorrente`, e
`Conta.receita_recorrente` virou `Conta.recorrencia`.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Categoria, Conta, ConfigUsuario, LancamentoRecorrente
from core.services.import_service import (
    CAMPOS_RENOMEADOS_POR_MODELO,
    NOMES_LEGADOS_DE_MODELO,
    _normalizar_campos_legados,
    restore_user_data_fcbk,
)

User = get_user_model()


class NormalizacaoDeCamposLegadosTests(TestCase):
    """Cobre a reescrita de chaves de registro para os nomes atuais."""

    def test_renomeia_chave_de_fk_da_conta(self):
        """`receita_recorrente_uuid` do formato antigo passa a `recorrencia_uuid`."""
        linha = {"descricao": "Salário", "receita_recorrente_uuid": "abc-123"}
        resultado = _normalizar_campos_legados("Conta", linha)

        self.assertEqual(resultado["recorrencia_uuid"], "abc-123")
        self.assertNotIn("receita_recorrente_uuid", resultado)

    def test_nao_sobrescreve_chave_nova_ja_presente(self):
        """Se o backup já é do formato novo, o valor atual prevalece."""
        linha = {"receita_recorrente_uuid": "antigo", "recorrencia_uuid": "novo"}
        resultado = _normalizar_campos_legados("Conta", linha)

        self.assertEqual(resultado["recorrencia_uuid"], "novo")

    def test_modelo_sem_renomeio_passa_intacto(self):
        """A normalização não deve inventar chaves em modelos não afetados."""
        linha = {"nome": "Mercado", "tipo": "D"}
        self.assertEqual(_normalizar_campos_legados("Categoria", linha), linha)

    def test_mapa_declara_o_rename_do_lancamento_recorrente(self):
        """Guarda o contrato: sem esta entrada, backups antigos perdem as regras."""
        self.assertIn(
            "ReceitaRecorrente",
            NOMES_LEGADOS_DE_MODELO["LancamentoRecorrente"],
        )
        self.assertEqual(
            CAMPOS_RENOMEADOS_POR_MODELO["Conta"]["receita_recorrente_uuid"],
            "recorrencia_uuid",
        )


class RestauracaoDeBackupLegadoTests(TestCase):
    """Restaura um payload no formato antigo e confere que nada se perde."""

    def setUp(self):
        """Cria um usuário limpo, com a configuração que a restauração espera."""
        self.user = User.objects.create_user(
            username="ana", password="senha-bem-comprida-123",
            email="ana@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)

    def _payload_legado(self) -> dict:
        """Monta um dicionário no formato gerado antes das renomeações.

        Returns:
            dict: Estrutura equivalente ao conteúdo de um `.fcbk` antigo.
        """
        return {
            "data": {
                "core": {
                    "Categoria": [
                        {
                            "uuid": "11111111-1111-1111-1111-111111111111",
                            "nome": "Salário",
                            "tipo": "R",
                            "is_default": False,
                        }
                    ],
                    # Chave de modelo no nome antigo.
                    "ReceitaRecorrente": [
                        {
                            "uuid": "22222222-2222-2222-2222-222222222222",
                            "descricao": "Salário mensal",
                            "valor": "5000.00",
                            "frequencia": "mensal",
                            "data_inicio": "2026-01-05",
                            "data_fim": None,
                            "ativa": True,
                            "categoria_uuid": "11111111-1111-1111-1111-111111111111",
                        }
                    ],
                    # Nome de modelo inalterado, mas chave de FK no nome antigo.
                    "Conta": [
                        {
                            "uuid": "33333333-3333-3333-3333-333333333333",
                            "tipo": "R",
                            "descricao": "Salário mensal",
                            "valor": "5000.00",
                            "data_prevista": "2026-01-05",
                            "transacao_realizada": False,
                            "data_realizacao": None,
                            "data_compra": None,
                            "eh_fatura_cartao": False,
                            "categoria_uuid": "11111111-1111-1111-1111-111111111111",
                            "cartao_uuid": None,
                            "receita_recorrente_uuid": "22222222-2222-2222-2222-222222222222",
                        }
                    ],
                }
            }
        }

    def test_regra_de_recorrencia_e_restaurada_da_chave_antiga(self):
        """Sem o mapa de nomes legados, a regra desapareceria sem erro."""
        restore_user_data_fcbk(self._payload_legado(), self.user)

        regra = LancamentoRecorrente.objects.get(usuario=self.user)
        self.assertEqual(regra.descricao, "Salário mensal")
        # Regras de antes da generalização são receitas, pelo default do campo.
        self.assertEqual(regra.tipo, LancamentoRecorrente.TIPO_RECEITA)

    def test_vinculo_entre_conta_e_regra_sobrevive_ao_rename_de_campo(self):
        """A ocorrência precisa continuar sabendo qual regra a gerou."""
        restore_user_data_fcbk(self._payload_legado(), self.user)

        conta = Conta.objects.get(usuario=self.user)
        regra = LancamentoRecorrente.objects.get(usuario=self.user)

        self.assertIsNotNone(
            conta.recorrencia_id,
            "A conta restaurada perdeu o vínculo com a regra de recorrência.",
        )
        self.assertEqual(conta.recorrencia_id, regra.id)

    def test_restauracao_preserva_os_demais_campos(self):
        """Confere que a normalização não danifica o resto do registro."""
        restore_user_data_fcbk(self._payload_legado(), self.user)

        conta = Conta.objects.get(usuario=self.user)
        self.assertEqual(conta.descricao, "Salário mensal")
        self.assertEqual(conta.data_prevista, date(2026, 1, 5))
        self.assertEqual(conta.tipo, Conta.TIPO_RECEITA)
        self.assertEqual(
            conta.categoria, Categoria.objects.get(usuario=self.user, nome="Salário")
        )
