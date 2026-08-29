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
    """Classe abstrata para auditoria de criação e modificação de registros."""
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
        tipo: Natureza da categoria ('R' para Receita, 'D' para Despesa, 'I' para Investimento).
        is_default: Define se é uma categoria global padrão do sistema.
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
        tipo: Tipo do lançamento ('R' para Receita, 'D' para Despesa, 'I' para Investimento).
        transacao_realizada: Indica se o lançamento foi liquidado (pago/recebido).
        eh_fatura_cartao: Identifica se este registro representa o pagamento consolidado de uma fatura de cartão.
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

    # Origem, caso esta ocorrência tenha sido gerada por uma regra de recorrência
    recorrencia = models.ForeignKey(
        "core.LancamentoRecorrente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias",
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
            data: A data de liquidação da conta. Defaults to timezone.localdate().
        """
        if self.transacao_realizada:
            return
        self.transacao_realizada = True
        self.data_realizacao = data or timezone.localdate()
        self.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )

        # Se for o pagamento da fatura consolidada do cartão, marca também as despesas individuais dela
        if self.eh_fatura_cartao and self.cartao:
            Conta.objects.filter(
                usuario=self.usuario,
                cartao=self.cartao,
                eh_fatura_cartao=False,
                data_prevista=self.data_prevista
            ).update(
                transacao_realizada=True,
                data_realizacao=self.data_realizacao
            )

    def desmarcar_realizada(self):
        """Desmarca o lançamento financeiro, retornando-o ao estado previsto/pendente."""
        self.transacao_realizada = False
        self.data_realizacao = None
        self.save(
            update_fields=["transacao_realizada", "data_realizacao", "atualizada_em"]
        )

        # Se for a fatura consolidada do cartão, desmarca também as despesas individuais dela
        if self.eh_fatura_cartao and self.cartao:
            Conta.objects.filter(
                usuario=self.usuario,
                cartao=self.cartao,
                eh_fatura_cartao=False,
                data_prevista=self.data_prevista
            ).update(
                transacao_realizada=False,
                data_realizacao=None
            )

    def save(self, *args, **kwargs):
        """Salva a transação sincronizando o estado com a fatura consolidada se aplicável.

        Caso seja uma compra individual de cartão e já exista uma fatura consolidada
        cadastrada para o mesmo período, a compra herda o estado da fatura (paga/pendente).
        """
        if self.cartao and not self.eh_fatura_cartao:
            if self.data_compra:
                from core.services.fatura_service import calcular_vencimento_fatura
                calculado = calcular_vencimento_fatura(
                    self.data_compra,
                    self.cartao.dia_fechamento,
                    self.cartao.dia_vencimento
                )
                if not self.data_prevista or self.data_prevista < calculado:
                    self.data_prevista = calculado

            fatura = self.__class__.objects.filter(
                usuario=self.usuario,
                cartao=self.cartao,
                eh_fatura_cartao=True,
                data_prevista=self.data_prevista
            ).first()
            if fatura:
                self.transacao_realizada = fatura.transacao_realizada
                self.data_realizacao = fatura.data_realizacao if fatura.transacao_realizada else None

        super().save(*args, **kwargs)


class LancamentoRecorrente(AuditoriaModel):
    """Regra de geração automática de lançamentos recorrentes, de receita ou de despesa.

    Não é um lançamento: as ocorrências são materializadas como `Conta` vinculadas via
    `recorrencia`, sob demanda, por `core.services.recorrencia_service`.

    Nasceu como `ReceitaRecorrente`. O campo `tipo` foi acrescentado porque a projeção
    de 12 meses ficava otimista sem despesas fixas — a receita era materializada um ano
    à frente, enquanto aluguel e assinaturas só existiam nos meses lançados à mão.
    Generalizar a regra existente evita manter dois motores de recorrência.

    Atributos:
        frequencia: Periodicidade de geração (mensal/quinzenal/semanal/anual).
        data_fim: Data limite opcional; indefinida se vazia.
        ativa: Se False, para a geração de novas ocorrências (histórico é preservado).
    """

    TIPO_RECEITA = "R"
    TIPO_DESPESA = "D"
    TIPO_CHOICES = (
        (TIPO_RECEITA, "Receita"),
        (TIPO_DESPESA, "Despesa"),
    )

    FREQ_MENSAL = "mensal"
    FREQ_QUINZENAL = "quinzenal"
    FREQ_SEMANAL = "semanal"
    FREQ_ANUAL = "anual"
    FREQUENCIA_CHOICES = (
        (FREQ_MENSAL, "Mensal"),
        (FREQ_QUINZENAL, "Quinzenal"),
        (FREQ_SEMANAL, "Semanal"),
        (FREQ_ANUAL, "Anual"),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lancamentos_recorrentes",
    )
    # Default de receita para que as regras já existentes, criadas quando o modelo
    # só cobria entradas, mantenham exatamente o comportamento anterior.
    tipo = models.CharField(
        max_length=1, choices=TIPO_CHOICES, default=TIPO_RECEITA, db_index=True
    )
    descricao = models.CharField(max_length=255, blank=True)
    categoria = models.ForeignKey(
        "core.Categoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lancamentos_recorrentes",
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    frequencia = models.CharField(max_length=10, choices=FREQUENCIA_CHOICES, default=FREQ_MENSAL)
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["-data_inicio"]
        verbose_name = "Lançamento Recorrente"
        verbose_name_plural = "Lançamentos Recorrentes"

    def __str__(self):
        return f"{self.descricao} ({self.get_tipo_display()}, {self.get_frequencia_display()})"


class ConfigUsuario(AuditoriaModel):
    """Configurações, preferências e estado de identidade de cada usuário.

    Os campos de verificação de e-mail ficam aqui, e não num modelo novo, porque este já
    é o perfil um-para-um do usuário, criado junto com a conta e herdando a auditoria de
    `AuditoriaModel`.

    O endereço confirmado permanece em `User.email`, onde o Django e o gerador de token
    de redefinição esperam encontrá-lo. `email_pendente` guarda o endereço novo até ser
    confirmado, sem que o usuário perca o acesso ao atual.

    Atributos:
        moeda_padrao: Código da moeda padrão do usuário (ex: BRL).
    """
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="config"
    )
    moeda_padrao = models.CharField(max_length=10, default="BRL")
    ultimo_export_em = models.DateTimeField(null=True, blank=True)
    email_verificado = models.BooleanField(default=False)
    email_verificado_em = models.DateTimeField(null=True, blank=True)
    email_pendente = models.EmailField(blank=True, default="")

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
        limite: Limite máximo de crédito aprovado.
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
        linhas_importadas: Quantidade total de registros conciliados/importados com sucesso.
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
    data_vencimento = models.DateField(
        null=True,
        blank=True,
        help_text="Data de vencimento da fatura associada a este extrato",
    )
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
        tipo: Natureza do lançamento ('C' para Crédito, 'D' para Débito).
        status: Estado da conciliação ('pendente', 'importado', 'ignorado').
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


class PlanoMetas(AuditoriaModel):
    """Base de cálculo do planejamento de metas financeiras de um usuário.

    Guarda os dois números que alimentam os múltiplos das metas padrão
    (renda mensal e custo de vida mensal). Ambos podem ser preenchidos
    automaticamente pela média dos últimos meses de lançamentos ou
    sobrescritos manualmente pelo usuário.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plano_metas",
    )
    renda_mensal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    custo_vida_mensal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    usar_valores_automaticos = models.BooleanField(default=True)
    meses_referencia = models.PositiveSmallIntegerField(default=3)

    class Meta:
        verbose_name = "Plano de Metas"
        verbose_name_plural = "Planos de Metas"

    def __str__(self):
        """Retorna a identificação do plano pelo usuário proprietário.

        Returns:
            str: Identificação legível do plano.
        """
        return f"Plano de metas de {self.usuario.username}"


class MetaFinanceira(AuditoriaModel):
    """Meta financeira de acúmulo ou teto de gastos.

    As quatro metas padrão derivam de múltiplos da renda ou do custo de vida
    (`core.services.metas_service.METAS_PADRAO`); o usuário também cadastra metas
    personalizadas com valor-alvo digitado. `natureza` distingue os comportamentos:
    acúmulo progride até o alvo, teto é limite mensal a não ultrapassar.

    Atributos:
        tipo: Identificador da meta padrão ou 'personalizada'.
        natureza: 'acumulo' (progride até o alvo) ou 'teto' (limite mensal).
        base_calculo: Origem do valor-alvo ('renda', 'custo_vida' ou 'manual').
        valor_acumulado: Acúmulo manual; ignorado quando `origem_acumulado` é 'carteira'.
        origem_acumulado: 'manual', 'carteira' (valor de mercado) ou 'aportes_mes'. As
            duas últimas são recalculadas a cada leitura por `metas_service`.
        ordem: Posição de exibição; as metas padrão ocupam as primeiras.
    """

    TIPO_PATRIMONIO_RENDA = "patrimonio_renda"
    TIPO_APORTE_MENSAL = "aporte_mensal"
    TIPO_RESERVA_EMERGENCIA = "reserva_emergencia"
    TIPO_GASTO_ESSENCIAL = "gasto_essencial"
    TIPO_PERSONALIZADA = "personalizada"

    TIPO_CHOICES = (
        (TIPO_PATRIMONIO_RENDA, "Patrimônio para viver de renda"),
        (TIPO_APORTE_MENSAL, "Meta mensal investimento"),
        (TIPO_RESERVA_EMERGENCIA, "Reserva de emergência"),
        (TIPO_GASTO_ESSENCIAL, "Limite de gastos essenciais"),
        (TIPO_PERSONALIZADA, "Personalizada"),
    )

    NATUREZA_ACUMULO = "acumulo"
    NATUREZA_TETO = "teto"
    NATUREZA_CHOICES = (
        (NATUREZA_ACUMULO, "Acúmulo"),
        (NATUREZA_TETO, "Teto mensal"),
    )

    BASE_RENDA = "renda"
    BASE_CUSTO_VIDA = "custo_vida"
    BASE_MANUAL = "manual"
    BASE_CHOICES = (
        (BASE_RENDA, "Renda mensal"),
        (BASE_CUSTO_VIDA, "Custo de vida mensal"),
        (BASE_MANUAL, "Valor manual"),
    )

    ORIGEM_MANUAL = "manual"
    ORIGEM_CARTEIRA = "carteira"
    ORIGEM_APORTES_MES = "aportes_mes"
    ORIGEM_CHOICES = (
        (ORIGEM_MANUAL, "Informado manualmente"),
        (ORIGEM_CARTEIRA, "Valor de mercado da carteira"),
        (ORIGEM_APORTES_MES, "Aportes do mês na carteira"),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="metas",
    )
    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default=TIPO_PERSONALIZADA)
    natureza = models.CharField(max_length=10, choices=NATUREZA_CHOICES, default=NATUREZA_ACUMULO)
    base_calculo = models.CharField(max_length=15, choices=BASE_CHOICES, default=BASE_MANUAL)
    multiplicador = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    valor_alvo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    valor_acumulado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    origem_acumulado = models.CharField(
        max_length=15, choices=ORIGEM_CHOICES, default=ORIGEM_MANUAL
    )
    prazo = models.DateField(null=True, blank=True)
    concluida = models.BooleanField(default=False)
    ordem = models.PositiveSmallIntegerField(default=99)
    observacao = models.TextField(blank=True)

    class Meta:
        unique_together = ("usuario", "nome")
        ordering = ["ordem", "id"]
        verbose_name = "Meta Financeira"
        verbose_name_plural = "Metas Financeiras"

    def acumulado_efetivo(self, valores_externos=None):
        """Acúmulo que vale para esta meta, respeitando a origem escolhida.

        Returns:
            float: Valor acumulado a considerar no progresso.
        """
        externo = (valores_externos or {}).get(self.origem_acumulado)
        if externo is not None:
            return float(externo)
        return float(self.valor_acumulado or 0)

    def progresso_percentual(self, valores_externos=None):
        """Percentual do alvo já atingido.

        Não é limitado a 100: uma meta de teto ultrapassada precisa reportar
        o excedente para que a interface possa sinalizar o estouro.

        Returns:
            float: Percentual atingido, ou 0.0 quando o alvo não é positivo.
        """
        if not self.valor_alvo or self.valor_alvo <= 0:
            return 0.0
        return self.acumulado_efetivo(valores_externos) / float(self.valor_alvo) * 100

    def valor_restante(self, valores_externos=None):
        """Quanto falta para atingir o alvo (nunca negativo).

        Returns:
            float: Diferença entre alvo e acumulado, com piso em zero.
        """
        restante = float(self.valor_alvo or 0) - self.acumulado_efetivo(valores_externos)
        return max(restante, 0.0)

    def __str__(self):
        """Retorna o nome da meta com seu valor-alvo.

        Returns:
            str: Resumo legível da meta.
        """
        return f"{self.nome} (R$ {self.valor_alvo})"


class AporteMeta(AuditoriaModel):
    """Registro histórico de um aporte feito em direção a uma meta.

    Cada aporte soma no `valor_acumulado` da meta no momento da criação —
    o campo da meta continua sendo a fonte da verdade do progresso, e este
    modelo serve como log auditável das contribuições.

    Atributos:
        observacao: Anotação curta e opcional sobre o aporte.
    """

    meta = models.ForeignKey(
        MetaFinanceira,
        on_delete=models.CASCADE,
        related_name="aportes",
    )
    data = models.DateField(default=timezone.localdate)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    observacao = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "Aporte de Meta"
        verbose_name_plural = "Aportes de Metas"

    def __str__(self):
        """Retorna data e valor do aporte.

        Returns:
            str: Resumo legível do aporte.
        """
        return f"{self.data} - R$ {self.valor}"


class LogAcaoAdmin(AuditoriaModel):
    """Registro imutável das ações administrativas sobre contas de usuário.

    Um painel capaz de suspender contas precisa deixar rastro de quem fez o quê e
    quando: sem isso, "minha conta foi bloqueada e ninguém sabe por quê" não tem
    resposta possível.

    Ambas as chaves usam `SET_NULL` em vez de `CASCADE`. Apagar a conta de um
    administrador não pode apagar o histórico do que ele fez — o registro perderia
    exatamente a informação que justifica a sua existência.
    """

    ACAO_SUSPENDER = "suspender"
    ACAO_REATIVAR = "reativar"
    ACAO_CHOICES = [
        (ACAO_SUSPENDER, "Suspender conta"),
        (ACAO_REATIVAR, "Reativar conta"),
    ]

    ator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acoes_admin_realizadas",
    )
    ator_username = models.CharField(max_length=150)
    alvo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acoes_admin_recebidas",
    )
    alvo_username = models.CharField(max_length=150)
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    detalhe = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "Log de ação administrativa"
        verbose_name_plural = "Logs de ações administrativas"

    def __str__(self):
        """Descreve a ação de forma legível.

        Returns:
            str: Resumo no formato "ator ação alvo".
        """
        return f"{self.ator_username} {self.get_acao_display()} {self.alvo_username}"
