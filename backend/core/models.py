"""
Modelos de Banco de Dados do Módulo Financeiro Core.

Este arquivo estabelece os esquemas relacionais do PostgreSQL para controle
de despesas, receitas, cartões de crédito e importações de extratos bancários,
todos vinculados a um UUID seguro e isolados por usuário (Multi-Tenant básico).
"""

from django.utils import timezone
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


# Create your models here.
import uuid


class AuditoriaModel(models.Model):
    """Classe abstrata para auditoria de criação e modificação de registros.

    Atributos:
        uuid (UUID): Identificador único universal gerado automaticamente.
        criada_em (datetime): Data e hora de criação do registro.
        atualizada_em (datetime): Data e hora da última modificação do registro.
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Categoria(AuditoriaModel):
    """Representa uma subdivisão financeira para classificação de transações.

    Categorias servem para agrupar despesas, receitas ou investimentos,
    possuindo isolamento por usuário.

    Atributos:
        usuario (User): Usuário proprietário da categoria.
        nome (str): Nome descritivo da categoria.
        tipo (str): Natureza da categoria ('R' para Receita, 'D' para Despesa, 'I' para Investimento).
        is_default (bool): Define se é uma categoria global padrão do sistema.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categorias",
    )

    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"
    TIPO_INVESTIMENTO = "I"

    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
        (TIPO_INVESTIMENTO, "Investimento"),
    )

    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ("usuario", "nome")
        ordering = ["nome"]

    def __str__(self):
        """Retorna a representação textual do nome da categoria.

        Returns:
            str: Nome da categoria.
        """
        return self.nome


class Conta(AuditoriaModel):
    """Modelo principal que representa lançamentos financeiros de receitas ou despesas.

    Controla o ciclo de vida completo de uma obrigação financeira (prevista, atrasada, paga),
    além de mapear transações a cartões de crédito ou categorias específicas.

    Atributos:
        usuario (User): O usuário proprietário deste lançamento financeiro.
        tipo (str): Tipo do lançamento ('R' para Receita, 'D' para Despesa, 'I' para Investimento).
        descricao (str): Descrição curta ou observação sobre o lançamento.
        valor (Decimal): Valor financeiro monetário da operação.
        data_prevista (date): Data de vencimento ou recebimento planejado.
        transacao_realizada (bool): Indica se o lançamento foi liquidado (pago/recebido).
        data_realizacao (date): Data real de liquidação física ou bancária.
        categoria (Categoria): Classificação da transação na árvore de categorias.
        cartao (CartaoCredito): Cartão de crédito associado caso seja uma despesa faturável.
        data_compra (date): Data em que a compra de fato ocorreu.
        eh_fatura_cartao (bool): Identifica se este registro representa o pagamento consolidado de uma fatura de cartão.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contas",
    )

    # Natureza
    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"
    TIPO_INVESTIMENTO = "I"
    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
        (TIPO_INVESTIMENTO, "Investimento"),
    )

    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    descricao = models.CharField(max_length=255, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)

    # Agendamento (equivale ao vencimento / data prevista)
    data_prevista = models.DateField(db_index=True)

    # Realização (equivale a “virou transação”)
    transacao_realizada = models.BooleanField(default=False, db_index=True)
    data_realizacao = models.DateField(null=True, blank=True, db_index=True)

    categoria = models.ForeignKey(
        "core.Categoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contas",
    )
    cartao = models.ForeignKey(
        "core.CartaoCredito",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="despesas",
    )

    # Data da compra (para despesas de cartão - diferente da data de vencimento)
    data_compra = models.DateField(null=True, blank=True, db_index=True)

    # Sistema de Fatura de Cartão
    eh_fatura_cartao = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marca se este registro é uma fatura de cartão (não uma despesa individual)",
    )

    class Meta:
        ordering = ["-data_prevista", "-id"]
        indexes = [
            models.Index(fields=["usuario", "tipo", "data_prevista"]),
            models.Index(fields=["usuario", "transacao_realizada", "data_realizacao"]),
        ]

    def __str__(self):
        """Retorna uma string descritiva da conta incluindo seu estado de liquidação.

        Returns:
            str: Descrição do lançamento financeiro.
        """
        status = "Realizada" if self.transacao_realizada else "Prevista"
        return (
            f"{status} {self.get_tipo_display()} - {self.valor} ({self.data_prevista})"
        )

    @property
    def esta_atrasada(self):
        """Verifica se o lançamento está com o pagamento atrasado em relação à data prevista.

        Returns:
            bool: True se estiver atrasada, False caso contrário.
        """
        # Atrasada = passou da data prevista e ainda não foi realizada
        return (not self.transacao_realizada) and (
            self.data_prevista < timezone.localdate()
        )

    def marcar_realizada(self, data=None):
        """Marca o lançamento financeiro como realizado (pago/recebido).

        Args:
            data (date, optional): A data de liquidação da conta. Defaults to timezone.localdate().
        """
        if self.transacao_realizada:
            return
        self.transacao_realizada = True
        self.data_realizacao = data or timezone.localdate()
        self.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )

    def desmarcar_realizada(self):
        """Desmarca o lançamento financeiro, retornando-o ao estado previsto/pendente."""
        self.transacao_realizada = False
        self.data_realizacao = None
        self.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )


class ConfigUsuario(AuditoriaModel):
    """Configurações e preferências personalizadas de cada usuário do sistema.

    Atributos:
        usuario (OneToOneField): Usuário proprietário das configurações.
        moeda_padrao (str): Código da moeda padrão do usuário (ex: BRL).
        ultimo_export_em (datetime): Registro da data e hora da última exportação de dados.
    """
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="config"
    )
    moeda_padrao = models.CharField(max_length=10, default="BRL")
    ultimo_export_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Retorna uma string que identifica o proprietário das configurações.

        Returns:
            str: Identificação das configurações do usuário.
        """
        return f"Configurações de {self.usuario.username}"


class CartaoCredito(AuditoriaModel):
    """Representa cartões de crédito pertencentes a um usuário.

    Controla limites de gastos, dia de fechamento de fatura, dia de vencimento,
    além de agrupar e calcular dinamicamente as despesas faturáveis associadas.

    Atributos:
        usuario (User): Usuário proprietário do cartão.
        nome (str): Nome de exibição ou apelido do cartão (ex: Nubank, Inter).
        bandeira (str): Bandeira do cartão (Visa, Mastercard, Elo, etc.).
        ultimos_digitos (str): Últimos 4 dígitos para identificação amigável.
        limite (Decimal): Limite máximo de crédito aprovado.
        dia_fechamento (int): Dia do mês em que ocorre o fechamento da fatura.
        dia_vencimento (int): Dia do mês em que vence o pagamento da fatura.
        ativo (bool): Flag de estado do cartão.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cartoes",
    )

    BANDEIRA_CHOICES = (
        ("VISA", "Visa"),
        ("MASTERCARD", "Mastercard"),
        ("ELO", "Elo"),
        ("AMEX", "American Express"),
        ("HIPERCARD", "Hipercard"),
        ("DINERS", "Diners Club"),
        ("OUTRO", "Outro"),
    )

    nome = models.CharField(max_length=100)  # Ex: "Nubank", "Inter", "C6"
    bandeira = models.CharField(max_length=20, choices=BANDEIRA_CHOICES, default="VISA")
    ultimos_digitos = models.CharField(max_length=4, blank=True)
    limite = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    dia_fechamento = models.IntegerField(default=1)  # Dia que fecha a fatura
    dia_vencimento = models.IntegerField(default=10)  # Dia que vence a fatura
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Cartão de Crédito"
        verbose_name_plural = "Cartões de Crédito"

    def __str__(self):
        """Retorna o nome amigável do cartão e seus últimos dígitos.

        Returns:
            str: Representação textual do cartão.
        """
        digitos = f" ****{self.ultimos_digitos}" if self.ultimos_digitos else ""
        return f"{self.nome}{digitos}"


class ExtratoImportado(AuditoriaModel):
    """Representa um lote/arquivo de extrato bancário importado pelo usuário.

    Facilita o processamento de conciliação bancária, armazenando metadados sobre
    o arquivo carregado (OFX ou outro), a instituição de origem e o status do processamento.

    Atributos:
        usuario (User): O usuário que realizou a importação.
        arquivo_nome (str): O nome original do arquivo carregado.
        banco (str): Instituição bancária do extrato (Nubank, Inter, Itaú, etc.).
        status (str): Estado atual da importação (Pendente, Processado, Erro).
        linhas_encontradas (int): Quantidade total de registros achados no extrato.
        linhas_importadas (int): Quantidade total de registros conciliados/importados com sucesso.
        erro_mensagem (str): Detalhamento técnico caso ocorra alguma falha na leitura.
        cartao (CartaoCredito): Cartão de crédito associado, caso seja um extrato de cartão.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="extratos_importados",
    )

    BANCO_CHOICES = (
        ("nubank", "Nubank"),
        ("inter", "Banco Inter"),
        ("itau", "Itaú"),
        ("bradesco", "Bradesco"),
        ("bb", "Banco do Brasil"),
        ("caixa", "Caixa Econômica"),
        ("santander", "Santander"),
        ("generico", "Genérico"),
    )

    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("processado", "Processado"),
        ("erro", "Erro"),
    )

    arquivo_nome = models.CharField(max_length=255)
    banco = models.CharField(max_length=20, choices=BANCO_CHOICES, default="generico")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    linhas_encontradas = models.IntegerField(default=0)
    linhas_importadas = models.IntegerField(default=0)
    erro_mensagem = models.TextField(blank=True)
    cartao = models.ForeignKey(
        "core.CartaoCredito",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extratos",
        help_text="Cartão de crédito associado a este extrato (opcional)",
    )

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "Extrato Importado"
        verbose_name_plural = "Extratos Importados"

    def __str__(self):
        """Retorna uma representação legível da origem do banco e o nome do arquivo.

        Returns:
            str: Banco e arquivo.
        """
        return f"{self.get_banco_display()} - {self.arquivo_nome}"


class LinhaExtrato(AuditoriaModel):
    """Representa uma linha individual extraída de um arquivo de extrato bancário.

    Contém os dados brutos obtidos do extrato que serão utilizados para a
    conciliação assistida de lançamentos, vinculando-se a uma Conta real
    após a confirmação do usuário.

    Atributos:
        extrato (ExtratoImportado): Lote de extrato pai desta linha.
        data (date): Data de competência da operação no banco.
        descricao (str): Descrição literal da transação no extrato bancário.
        valor (Decimal): Valor monetário bruto da operação.
        tipo (str): Natureza do lançamento ('C' para Crédito, 'D' para Débito).
        status (str): Estado da conciliação ('pendente', 'importado', 'ignorado').
        conta_vinculada (Conta): Lançamento financeiro real correspondente a esta linha.
    """

    extrato = models.ForeignKey(
        ExtratoImportado,
        on_delete=models.CASCADE,
        related_name="linhas",
    )

    TIPO_CREDITO = "C"
    TIPO_DEBITO = "D"
    TIPO_CHOICES = (
        (TIPO_CREDITO, "Crédito"),
        (TIPO_DEBITO, "Débito"),
    )

    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("importado", "Importado"),
        ("ignorado", "Ignorado"),
    )

    data = models.DateField()
    descricao = models.CharField(max_length=500)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    conta_vinculada = models.ForeignKey(
        Conta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linhas_extrato",
    )

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "Linha de Extrato"
        verbose_name_plural = "Linhas de Extrato"

    def __str__(self):
        """Retorna uma string resumida com data, descrição curta e valor da linha.

        Returns:
            str: Resumo amigável da linha de extrato.
        """
        return f"{self.data} - {self.descricao[:30]} - R$ {self.valor}"
