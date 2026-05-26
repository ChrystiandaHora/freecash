# 💻 FreeCash - Frontend

Esta é a interface reativa e moderna do ecossistema **FreeCash**, construída como uma SPA (Single Page Application) em **React 19** e **Vite 6+**, utilizando **Tailwind CSS v4** para uma estilização ultra-veloz e de alta performance.

---

## 🛠 Tech Stack & Bibliotecas Chave

*   **Core**: [React 19](https://react.dev/) & [Vite](https://vite.dev/) (Build tool e servidor de desenvolvimento otimizado via ES Modules).
*   **Estilização**: [Tailwind CSS v4](https://tailwindcss.com/) - Compilação nativa ultra veloz baseada em CSS moderno.
*   **Gerenciamento de Estado & Cache**: [@tanstack/react-query](https://tanstack.com/query/latest) (React Query) para sincronização e cache eficiente de chamadas à API, garantindo atualizações otimistas e sem loading desnecessários.
*   **Roteamento**: [React Router Dom v7](https://reactrouter.com/) para gerenciamento dinâmico de rotas privadas e públicas na SPA.
*   **Formulários & Validação**: [React Hook Form](https://react-hook-form.com/) integrado ao [Zod](https://zod.dev/) para validação robusta de inputs e tipagem no cliente.
*   **Visualização Gráfica**: [ApexCharts & React ApexCharts](https://apexcharts.com/) para a geração de gráficos de fluxo de caixa e alocação patrimonial.
*   **Ícones**: [Lucide React](https://lucide.dev/) para uma biblioteca consistente de ícones vetoriais.

---

## 📂 Estrutura de Pastas

A estrutura da pasta `frontend/src` foi projetada seguindo as melhores práticas de organização em React:

```text
src/
├── components/         # Componentes UI atômicos e reutilizáveis (botões, inputs, cards, modais)
├── layouts/            # Layouts estruturais de página (ex: Sidebar, Navbar, MainLayout)
├── pages/              # Componentes de página inteira (Dashboard, Investimentos, Extratos, Login, etc.)
├── services/           # Camada de comunicação com a API REST
│   ├── api.js          # Instância configurada do Axios (com interceptors de JWT)
│   └── queries/        # Custom hooks do React Query organizados por domínios de negócio
├── App.jsx             # Definição de provedores (QueryClient, Auth) e rotas globais
└── main.jsx            # Ponto de entrada da aplicação
```

---

## ⚡ Desenvolvimento Local

### Pré-requisitos
Certifique-se de possuir o [Node.js 20+](https://nodejs.org/) instalado no seu host.

### 1. Instalar as Dependências
Navegue até a pasta `frontend` e execute:
```bash
npm install
```

### 2. Configurar Variáveis de Ambiente
Crie um arquivo `.env` na raiz da pasta `frontend` (ou utilize o padrão do orquestrador do projeto):
```env
VITE_API_URL=http://localhost:8000
```
*Nota: Se o backend estiver rodando em uma porta remapeada pelo orquestrador (ex: `8001`), ajuste este valor.*

### 3. Iniciar o Servidor de Desenvolvimento
```bash
npm run dev
```
Acesse [http://localhost:5173](http://localhost:5173) no seu navegador.

---

## 🚀 Comandos Disponíveis

| Script | Descrição |
| :--- | :--- |
| `npm run dev` | Inicia o servidor de desenvolvimento do Vite com HMR ativo. |
| `npm run build` | Compila o projeto otimizando o bundle para produção na pasta `dist`. |
| `npm run preview` | Executa localmente o build de produção gerado para validação. |
| `npm run lint` | Roda a análise estática do ESLint para garantir a qualidade de código. |
