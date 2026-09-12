"""Testes de compatibilidade da restauração com backups de versões anteriores.

As chaves do `.fcbk` são nomes de classe de modelo e de campo, o que torna qualquer
renomeação no código uma quebra de formato de arquivo. O modo de falha é o pior
possível num backup: a restauração não dá erro, apenas não encontra os registros e
devolve a base sem eles.

Casos cobertos:

- `ReceitaRecorrente` virou `LancamentoRecorrente`, e `Conta.receita_recorrente`
  virou `Conta.recorrencia`;
- `Transacao.carteira` passou a existir e a ser obrigatória, e backups anteriores
  não trazem `carteira_uuid`;
- `Ativo.meta_porcentagem` mudou de modelo e passou a viver em
  `PosicaoCarteira.meta_porcentagem`.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Categoria, Conta, ConfigUsuario, LancamentoRecorrente
from core.services.import_service import (
    CAMPOS_MOVIDOS_DE_MODELO,
    CAMPOS_RENOMEADOS_POR_MODELO,
    FKS_LEGADAS_COM_PADRAO,
    NOMES_LEGADOS_DE_MODELO,
    _normalizar_campos_legados,
    restore_user_data_fcbk,
)
from investimento.models import Ativo, Carteira, Transacao

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


class RestauracaoDeBackupSemCarteiraTests(TestCase):
    """Restaura um `.fcbk` anterior às carteiras e confere que nada é descartado.

    É o teste mais importante desta feature. `Transacao.carteira` é NOT NULL, e o
    laço genérico da restauração grava `None` em toda FK cujo `<campo>_uuid` não
    esteja no arquivo. Sem o mapa `FKS_LEGADAS_COM_PADRAO`, o insert seria rejeitado,
    o fallback falharia também, e as ordens do usuário sumiriam **sem erro nenhum** —
    exatamente o modo de falha que a restauração não pode ter.
    """

    def setUp(self):
        """Cria um usuário limpo, com a configuração que a restauração espera."""
        self.user = User.objects.create_user(
            username="bruno", password="senha-bem-comprida-123",
            email="bruno@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)

    def _payload_sem_carteira(self) -> dict:
        """Monta o conteúdo de um backup gerado antes de a carteira existir.

        Returns:
            dict: Estrutura de `.fcbk` com ativo e transações, e nenhuma carteira.
        """
        return {
            "data": {
                "investimento": {
                    "Ativo": [
                        {
                            "uuid": "44444444-4444-4444-4444-444444444444",
                            "ticker": "PETR4",
                            "nome": "Petrobras",
                            "moeda": "BRL",
                            "ativo": True,
                            "quantidade": "100.00000000",
                            "preco_medio": "30.0000",
                            "subcategoria_uuid": None,
                        }
                    ],
                    "Transacao": [
                        {
                            "uuid": "55555555-5555-5555-5555-555555555555",
                            "tipo": "C",
                            "data": "2026-01-10",
                            "quantidade": "100.00000000",
                            "preco_unitario": "30.0000",
                            "taxas": "0.00",
                            "valor_total": "3000.00",
                            "ativo_uuid": "44444444-4444-4444-4444-444444444444",
                        }
                    ],
                }
            }
        }

    def test_transacao_de_backup_antigo_nao_e_descartada(self):
        """O caso que motivou o mapa: a ordem tem de sobreviver à restauração."""
        restore_user_data_fcbk(self._payload_sem_carteira(), self.user)

        transacoes = Transacao.objects.filter(usuario=self.user)
        self.assertEqual(
            transacoes.count(), 1,
            "A ordem do backup antigo foi descartada em silêncio na restauração.",
        )
        self.assertEqual(transacoes.first().valor_total, Decimal("3000.00"))

    def test_transacao_restaurada_cai_numa_carteira_concreta(self):
        """Sem custódia atribuída, a ordem não apareceria em filtro nenhum."""
        restore_user_data_fcbk(self._payload_sem_carteira(), self.user)

        transacao = Transacao.objects.get(usuario=self.user)
        self.assertIsNotNone(transacao.carteira_id)
        self.assertEqual(transacao.carteira.usuario_id, self.user.id)

    def test_posicao_por_carteira_e_reconstruida(self):
        """O recálculo pós-restauração precisa materializar a posição na custódia."""
        restore_user_data_fcbk(self._payload_sem_carteira(), self.user)

        ativo = Ativo.objects.get(usuario=self.user, ticker="PETR4")
        posicao = ativo.posicoes.get()
        self.assertEqual(posicao.quantidade, Decimal("100"))
        self.assertEqual(posicao.preco_medio, Decimal("30.0000"))

    def test_mapa_declara_a_fk_de_carteira(self):
        """Guarda o contrato: sem esta entrada, backups antigos perdem as ordens."""
        self.assertIn("carteira", FKS_LEGADAS_COM_PADRAO["Transacao"])

    def test_carteira_padrao_e_reaproveitada_e_nao_duplicada(self):
        """Restaurar duas vezes não pode encher a conta de carteiras órfãs."""
        restore_user_data_fcbk(self._payload_sem_carteira(), self.user)
        restore_user_data_fcbk(self._payload_sem_carteira(), self.user)

        self.assertEqual(Carteira.objects.filter(usuario=self.user).count(), 1)


class RestauracaoDeMetaLegadaTests(TestCase):
    """Restaura um `.fcbk` cuja meta de alocação ainda vivia no ativo.

    A meta era um campo de `Ativo` e passou a ser de `PosicaoCarteira`, para poder
    somar 100% dentro de cada custódia. `filter_valid_fields` descarta o que não
    existe mais no modelo, então sem a compatibilidade a meta some sem erro e o
    balanceamento reabre com todos os ativos em 0% — a tela fica inútil sem que nada
    tenha falhado.
    """

    def setUp(self):
        """Cria um usuário limpo, com a configuração que a restauração espera."""
        self.user = User.objects.create_user(
            username="carla", password="senha-bem-comprida-123",
            email="carla@exemplo.com",
        )
        ConfigUsuario.objects.get_or_create(usuario=self.user)

    def _payload_com_meta_no_ativo(self, meta: str = "35.50") -> dict:
        """Monta um backup anterior às carteiras, com a meta gravada no ativo.

        Returns:
            dict: Estrutura de `.fcbk` com ativo, meta e a ordem que gera a posição.
        """
        return {
            "data": {
                "investimento": {
                    "Ativo": [
                        {
                            "uuid": "66666666-6666-6666-6666-666666666666",
                            "ticker": "HGLG11",
                            "nome": "CSHG Logística FII",
                            "moeda": "BRL",
                            "ativo": True,
                            "quantidade": "100.00000000",
                            "preco_medio": "160.0000",
                            "meta_porcentagem": meta,
                            "subcategoria_uuid": None,
                        }
                    ],
                    "Transacao": [
                        {
                            "uuid": "77777777-7777-7777-7777-777777777777",
                            "tipo": "C",
                            "data": "2026-01-10",
                            "quantidade": "100.00000000",
                            "preco_unitario": "160.0000",
                            "taxas": "0.00",
                            "valor_total": "16000.00",
                            "ativo_uuid": "66666666-6666-6666-6666-666666666666",
                        }
                    ],
                }
            }
        }

    def test_meta_do_ativo_sobrevive_na_posicao(self):
        """O caso que motivou o mapa: a meta não pode voltar zerada."""
        restore_user_data_fcbk(self._payload_com_meta_no_ativo(), self.user)

        ativo = Ativo.objects.get(usuario=self.user, ticker="HGLG11")
        self.assertEqual(
            ativo.posicoes.get().meta_porcentagem, Decimal("35.50"),
            "A meta de alocação do backup antigo foi descartada em silêncio.",
        )

    def test_backup_sem_meta_no_ativo_nao_inventa_valor(self):
        """Backup do formato atual não passa por aqui: a meta já vem na posição."""
        payload = self._payload_com_meta_no_ativo()
        del payload["data"]["investimento"]["Ativo"][0]["meta_porcentagem"]

        restore_user_data_fcbk(payload, self.user)

        ativo = Ativo.objects.get(usuario=self.user, ticker="HGLG11")
        self.assertEqual(ativo.posicoes.get().meta_porcentagem, Decimal("0"))

    def test_meta_zerada_no_backup_e_preservada(self):
        """Zero explícito é intenção do usuário, e não ausência de dado."""
        restore_user_data_fcbk(self._payload_com_meta_no_ativo("0.00"), self.user)

        ativo = Ativo.objects.get(usuario=self.user, ticker="HGLG11")
        self.assertEqual(ativo.posicoes.get().meta_porcentagem, Decimal("0"))

    def test_restaurar_duas_vezes_mantem_a_meta(self):
        """A restauração é substituição total; a meta tem de reaparecer igual."""
        restore_user_data_fcbk(self._payload_com_meta_no_ativo(), self.user)
        restore_user_data_fcbk(self._payload_com_meta_no_ativo(), self.user)

        ativo = Ativo.objects.get(usuario=self.user, ticker="HGLG11")
        self.assertEqual(ativo.posicoes.get().meta_porcentagem, Decimal("35.50"))

    def test_mapa_declara_o_campo_movido(self):
        """Guarda o contrato: sem esta entrada, backups antigos perdem as metas."""
        self.assertEqual(
            CAMPOS_MOVIDOS_DE_MODELO["Ativo"]["meta_porcentagem"], "PosicaoCarteira"
        )
