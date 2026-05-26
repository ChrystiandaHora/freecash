# 🐍 FreeCash Backend Standards & REST API Playbook

This document defines the Django + Django REST Framework architecture, serialization rules, ViewSet routing, database optimization, DRE calculations, Excel backup services, and testing protocols for the **FreeCash** SaaS application.

---

## 📂 1. Django App Structure & Routing (Decoupled SPA Backend)

The FreeCash backend runs as a decoupled, headless API located in the `/backend/` directory. It exposes structured JSON payloads to the React frontend.

The backend utilizes modular Django apps for clean separation of concerns:
*   `core/`: Hosts core models (Accounts, Transactions, Credit Cards, Categories), backend utilities, and Excel import/export systems.
*   `investimento/`: Hosts assets, transactions, classes, and portfolio balance calculators.
*   `freecash/`: Standard Django settings, root URLs, and WSGI/ASGI configurations.

### 🛣️ API Endpoints Prefix
All REST APIs are registered in `freecash/urls.py` under the `/api/` prefix. Finance and transaction routes are isolated under the `/api/financeiro/` namespace:
*   `/api/financeiro/contas-pagar/`: Payable accounts (expenses).
*   `/api/financeiro/receitas/`: Receivables (revenues).
*   `/api/financeiro/cartoes/`: Credit Card portfolio metrics.
*   `/api/financeiro/transacoes/`: All transactions filtered by period.
*   `/api/relatorios/dre/`: Annual cash-flow Demonstração de Resultado do Exercício.
*   `/api/ferramentas/importar/` & `/api/ferramentas/exportar/`: Backup import and export endpoints.

---

## 💾 2. Serializer Design Patterns

Serializers must be built defensively to ensure database constraints and client expectations align smoothly.

### 🔹 2.1 Schema Mapping Standards
When mapping request formats to database fields, serializers must dynamically adapt data types:
*   **Dates Representation**: Frontends expect `data_vencimento` or `data_recebimento` for specific actions. Serializers must map these fields to the underlying database model field `data_prevista`.
*   **Representation Overrides**: Override `to_representation` to return detailed contextual structures (e.g. including current invoice balance, last 8 card purchases, or localized categories) without requiring the client to perform multiple sub-queries.

### 🔹 2.2 Category Auto-Resolution (Lazy String Mapping)
The frontend sends categories as plain string names (e.g., `categoria: "Alimentação"`). Serializers/ViewSets must not reject requests with validation errors requiring internal database primary keys. Instead:
1.  Intercept the input string in `create`/`perform_create`.
2.  Use `Categoria.objects.get_or_create(nome=categoria_str, usuario=request.user, tipo=correct_type)` to resolve the foreign key lazily.
3.  Inject the resolved Category ID into the instance instantiation pipeline.

---

## 🛡️ 3. Multi-Tenant Query Isolation (Mandatory)

To prevent Horizontal Privilege Escalation, **every** API endpoint must strictly isolate queries to the currently authenticated user.

*   **Rule**: Never write generic `queryset = Model.objects.all()` inside ViewSets without overriding `get_queryset`.
*   **Secure Implementation Example**:
    ```python
    class ContasPagarViewSet(viewsets.ModelViewSet):
        serializer_class = ContasPagarAPISerializer
        
        def get_queryset(self):
            # Enforces tenant boundary
            return Conta.objects.filter(
                usuario=self.request.user, 
                tipo='D'
            ).order_by('-data_prevista')
            
        def perform_create(self, serializer):
            # Enforces tenant ownership during insertion
            serializer.save(usuario=self.request.user, tipo='D')
    ```

---

## 🚀 4. Performance & Database Optimizations

To maintain a fast SaaS experience and prevent server overload:

### ⚡ 4.1 N+1 Query Elimination
Always preload related foreign key fields when returning sets of transactions or credit card purchases.
*   **Use `select_related`** for single-valued relationships (e.g. `category`, `user`, `credit_card`).
*   **Use `prefetch_related`** for multi-valued relationships.
*   **Example**:
    ```python
    def get_queryset(self):
        return Conta.objects.filter(usuario=self.request.user).select_related('categoria', 'cartao')
    ```

### ⚡ 4.2 Aggregated Database Computations
Never loop over database rows in Python to compute simple totals or averages. Perform calculations at the database level using `Sum` and `Case/When`:
```python
# Fast, single database query instead of N iterations
fatura_total = Conta.objects.filter(
    usuario=self.request.user,
    cartao=card_instance,
    transacao_realizada=False
).aggregate(total=Sum('valor'))['total'] or 0
```

---

## 📊 5. DRE Annual Calculation Engine

The DRE endpoint (`RelatoriosDREAPIView`) consolidates cash flow results by month and year. It must dynamically fetch:
1.  **Operating Revenue (Receita Bruta)**: Monthly summation of realized revenues (`tipo='R'`).
2.  **Operating Expenses (Despesas)**: Monthly realized expenses (`tipo='D'`), excluding variables that already transit through credit cards.
3.  **Credit Card Invoices**: Variable credit card expenditures grouped by the planned card invoice closure month.
4.  **Financial Result (Investimentos)**: Monthly dividends, portfolio profitability, and dividends received.
5.  **Calculated Net Profit (Resultado Líquido)**: Computed in Python as `Operating Revenue - Operating Expenses - Card Expenses + Investments`.

---

## 📥 6. Excel Backup Import/Export Service Engine

FreeCash features a robust backup service (`core/services/import_service.py` and `export_service.py`) designed to allow users to export and import their financial and investment history via standard Excel spreadsheets (`.xlsx`).

### 🔹 6.1 Data Integrity & Constraint Safety
*   **UUID Mapping**: Spreadsheet rows use stable UUIDs rather than database auto-incrementing integer PKs to prevent collision and data leaks when transferring data between accounts or staging areas. If a UUID is missing or invalid, the systems must auto-populate them safely.
*   **Validation Layer**: Every spreadsheet sheet (Categories, Accounts, Credit Cards, Transactions, Investments) must undergo comprehensive validation for types, date formats, and values using `pandas`.
*   **Lazy Resolution**: Foreign key relations (such as linking a transaction to a category or credit card) are resolved on-the-fly. If a related entity does not exist, it is either resolved via logical default values or created lazily under the requesting user's tenant boundary.

### 🔹 6.2 Transactional Import
To prevent partial, corrupted imports:
*   All import operations must run inside a strict Django `transaction.atomic()` database context. If any row fails validation or constraint verification, the entire import is rolled back immediately.

---

## 🧪 7. Backend Testing & Coverage Standards

To ensure mathematical precision and security enforcement, the backend maintains a robust automated test suite.

### 🔹 7.1 Test Structure & Organization
*   Tests must be split into logical test files within the `<app>/tests/` directory rather than written inside a single monolithic `tests.py` file:
    *   `test_models.py`: Tests for model constraints, triggers, and signals (e.g., position auto-recalculation triggers in `investimento/signals.py`).
    *   `test_services.py`: Tests for service-layer calculation engines, Excel parsing, and report generators.
    *   `test_api_auth.py` & `test_security.py`: Tests for JWT tokens, endpoints, and multi-tenant security queries.
*   **Coverage Target**: **>=80% test coverage** is strictly enforced for all service packages, calculators, and API views.

### 🔹 7.2 Running the Test Suite
Developers must run the backend test suite before opening any Pull Request:
```bash
# Run all tests
./.venv/bin/python manage.py test

# Run tests with coverage reporting
coverage run --source='.' manage.py test
coverage report -m
```
