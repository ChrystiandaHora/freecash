"""Testes do backup em ZIP: arquivos comuns (JSON e CSV) dentro de um ZIP AES-256.

O ZIP substituiu o `.fcbk`, que só o freecash conseguia ler. O conteúdo precisa abrir em
ferramentas comuns e, ao mesmo tempo, voltar para o sistema sem perda — por isso a
importação lê só o `dados.json`, e os CSVs existem para pessoas.
"""

import csv
import io
import json
import uuid
from datetime import date
from decimal import Decimal
from unittest import mock

import pyzipper
from django.contrib.auth.models import User
from django.test import TestCase

from core.models import CartaoCredito, Categoria, Conta
from core.services.export_service import gerar_backup_zip
from core.services.import_service import (
    importar_universal,
    ler_backup_zip,
    restaurar_dados_usuario,
)
from core.tests.backup_utils import SENHA_DE_TESTE, exportar_e_ler


def _zip_comum(arquivos: dict) -> io.BytesIO:
    """Monta um ZIP sem senha, como o que se recompacta numa ferramenta qualquer."""
    buffer = io.BytesIO()
    with pyzipper.ZipFile(buffer, "w") as zf:
        for nome, conteudo in arquivos.items():
            zf.writestr(nome, conteudo)
    buffer.seek(0)
    return buffer


class BackupZipTests(TestCase):
    """Conteúdo, ida e volta e recusas do backup em ZIP."""

    def setUp(self):
        self.user = User.objects.create_user(username="zipado", password="senha-forte-123")
        self.categoria = Categoria.objects.create(
            usuario=self.user, nome="Mercado", tipo=Categoria.TIPO_DESPESA
        )
        self.cartao = CartaoCredito.objects.create(
            usuario=self.user, nome="Nubank", dia_fechamento=3, dia_vencimento=10
        )
        self.conta = Conta.objects.create(
            usuario=self.user,
            tipo=Conta.TIPO_DESPESA,
            descricao="Compra do mês; feira e açougue",
            valor=Decimal("1234.56"),
            data_prevista=date(2026, 9, 10),
            categoria=self.categoria,
        )
        self.zip = gerar_backup_zip(self.user, SENHA_DE_TESTE)

    def _abrir(self) -> pyzipper.AESZipFile:
        zf = pyzipper.AESZipFile(io.BytesIO(self.zip))
        zf.setpassword(SENHA_DE_TESTE.encode())
        return zf

    # ── Conteúdo ─────────────────────────────────────────────────────────────

    def test_todas_as_entradas_sao_cifradas(self):
        with pyzipper.AESZipFile(io.BytesIO(self.zip)) as zf:
            self.assertTrue(all(info.flag_bits & 0x1 for info in zf.infolist()))
            with self.assertRaises(RuntimeError):
                zf.read("dados.json")

    def test_traz_leia_me_dados_e_planilhas(self):
        with self._abrir() as zf:
            nomes = set(zf.namelist())

        self.assertIn("LEIA-ME.txt", nomes)
        self.assertIn("dados.json", nomes)
        self.assertIn("planilhas/lancamentos.csv", nomes)
        self.assertIn("planilhas/categorias.csv", nomes)
        self.assertIn("planilhas/cartoes-de-credito.csv", nomes)

    def test_dados_json_identifica_formato_e_versao(self):
        with self._abrir() as zf:
            metadata = json.loads(zf.read("dados.json"))["metadata"]

        self.assertEqual(metadata["formato"], "freecash-dados")
        self.assertEqual(metadata["version"], "5.0")

    def test_planilha_abre_no_excel_em_portugues(self):
        with self._abrir() as zf:
            bruto = zf.read("planilhas/lancamentos.csv")

        self.assertTrue(bruto.startswith("﻿".encode("utf-8")))
        linhas = list(csv.DictReader(io.StringIO(bruto.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["descricao"], "Compra do mês; feira e açougue")
        self.assertEqual(linhas[0]["valor"], "1234,56")
        self.assertEqual(linhas[0]["data_prevista"], "2026-09-10")

    def test_planilha_traz_o_nome_ao_lado_do_identificador(self):
        with self._abrir() as zf:
            bruto = zf.read("planilhas/lancamentos.csv").decode("utf-8-sig")

        linha = next(csv.DictReader(io.StringIO(bruto), delimiter=";"))
        self.assertEqual(linha["categoria_uuid"], str(self.categoria.uuid))
        self.assertEqual(linha["categoria"], "Mercado")

    def test_leia_me_explica_como_abrir_e_lista_as_planilhas(self):
        with self._abrir() as zf:
            leia_me = zf.read("LEIA-ME.txt").decode("utf-8")

        self.assertIn("7-Zip", leia_me)
        self.assertIn("planilhas/lancamentos.csv", leia_me)
        self.assertIn("dados.json", leia_me)

    def test_zip_de_um_usuario_nao_contem_dados_de_outro(self):
        outro = User.objects.create_user(username="vizinho", password="senha-forte-123")
        Conta.objects.create(
            usuario=outro,
            tipo=Conta.TIPO_DESPESA,
            descricao="Segredo do vizinho",
            valor=Decimal("10.00"),
            data_prevista=date(2026, 9, 1),
        )

        with self._abrir() as zf:
            conteudo = b"".join(zf.read(nome) for nome in zf.namelist())

        self.assertNotIn("Segredo do vizinho".encode("utf-8"), conteudo)

    # ── Ida e volta ──────────────────────────────────────────────────────────

    def test_ida_e_volta_restaura_os_registros(self):
        dados = exportar_e_ler(self.user)
        Conta.objects.filter(usuario=self.user).delete()

        restaurar_dados_usuario(dados, self.user)

        conta = Conta.objects.get(uuid=self.conta.uuid)
        self.assertEqual(conta.valor, Decimal("1234.56"))
        self.assertEqual(conta.categoria.uuid, self.categoria.uuid)
        self.assertTrue(CartaoCredito.objects.filter(uuid=self.cartao.uuid).exists())

    def test_importar_aceita_o_zip_gerado(self):
        arquivo = io.BytesIO(self.zip)
        arquivo.name = "freecash_meus-dados.zip"

        resultado = importar_universal(arquivo, self.user, password=SENHA_DE_TESTE)

        self.assertGreater(resultado["criados"], 0)
        self.assertTrue(Conta.objects.filter(uuid=self.conta.uuid).exists())

    def test_aceita_zip_recompactado_sem_senha(self):
        with self._abrir() as zf:
            dados_json = zf.read("dados.json")

        dados = ler_backup_zip(_zip_comum({"dados.json": dados_json}), None)

        self.assertEqual(dados["metadata"]["formato"], "freecash-dados")

    # ── Recusas ──────────────────────────────────────────────────────────────

    def test_recusa_senha_errada(self):
        with self.assertRaisesMessage(ValueError, "Senha incorreta"):
            ler_backup_zip(io.BytesIO(self.zip), "outra-senha-qualquer")

    def test_recusa_zip_cifrado_sem_senha(self):
        with self.assertRaisesMessage(ValueError, "protegido por senha"):
            ler_backup_zip(io.BytesIO(self.zip), None)

    def test_recusa_zip_sem_dados_json(self):
        with self.assertRaisesMessage(ValueError, "dados.json"):
            ler_backup_zip(_zip_comum({"outro.txt": "nada"}), None)

    def test_recusa_arquivo_que_nao_e_zip(self):
        with self.assertRaisesMessage(ValueError, "ZIP"):
            ler_backup_zip(io.BytesIO(b"isto nao e um zip"), None)

    def test_recusa_formato_desconhecido(self):
        conteudo = json.dumps({"metadata": {"formato": "outro-app", "version": "5.0"}, "data": {}})

        with self.assertRaisesMessage(ValueError, "não foi gerado pelo freecash"):
            ler_backup_zip(_zip_comum({"dados.json": conteudo}), None)

    def test_recusa_versao_nao_suportada(self):
        conteudo = json.dumps(
            {"metadata": {"formato": "freecash-dados", "version": "99.0"}, "data": {}}
        )

        with self.assertRaisesMessage(ValueError, "Versão"):
            ler_backup_zip(_zip_comum({"dados.json": conteudo}), None)

    def test_recusa_dados_json_acima_do_teto(self):
        with mock.patch("core.services.import_service.TAMANHO_MAXIMO_DADOS_JSON", 100):
            with self.assertRaisesMessage(ValueError, "grande demais"):
                ler_backup_zip(io.BytesIO(self.zip), SENHA_DE_TESTE)

    # ── Arquivo editado à mão ────────────────────────────────────────────────

    def _categoria_forjada(self, **campos) -> dict:
        dados = exportar_e_ler(self.user)
        modelo = dados["data"]["core"]["Categoria"][0]
        dados["data"]["core"]["Categoria"].append(
            dict(modelo, uuid=str(uuid.uuid4()), nome="Intrusa", **campos)
        )
        return dados

    def test_arquivo_forjado_nao_cria_registro_na_conta_de_outro_usuario(self):
        outro = User.objects.create_user(username="vitima", password="senha-forte-123")

        restaurar_dados_usuario(self._categoria_forjada(usuario_id=outro.pk), self.user)

        self.assertFalse(Categoria.objects.filter(usuario=outro, nome="Intrusa").exists())
        self.assertTrue(Categoria.objects.filter(usuario=self.user, nome="Intrusa").exists())

    def test_arquivo_forjado_nao_sobrescreve_registro_alheio_pelo_id(self):
        outro = User.objects.create_user(username="vitima", password="senha-forte-123")
        alheia = Categoria.objects.create(usuario=outro, nome="Da vítima", tipo=Categoria.TIPO_DESPESA)

        restaurar_dados_usuario(self._categoria_forjada(id=alheia.pk), self.user)

        alheia.refresh_from_db()
        self.assertEqual((alheia.usuario, alheia.nome), (outro, "Da vítima"))
        self.assertTrue(Categoria.objects.filter(usuario=self.user, nome="Intrusa").exists())

    def test_importar_recusa_extensao_fcbk(self):
        arquivo = io.BytesIO(b"conteudo antigo")
        arquivo.name = "backup_freecash.fcbk"

        with self.assertRaisesMessage(ValueError, ".zip"):
            importar_universal(arquivo, self.user, password="qualquer")
