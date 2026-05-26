# 🎨 FreeCash Frontend Standards & Playbook

This document defines the React SPA architecture, reusable UI component standards, ApexCharts lifecycles, state cache management, and UX/UI conventions for the frontend application (built with **React 19**, **Vite**, and **Tailwind CSS v4**).

---

## 📂 1. Directory Structure & Organization

All frontend code resides under `/frontend/src/` and must strictly adhere to the following modular organization:

*   `components/`: Reusable, atomic components.
    *   `ui/`: Base visual primitives (Button, Input, Accordion, Badge, Card, Progress, etc.) designed using flat, premium visual tokens.
    *   `DashboardLayout.jsx`: Master navigation wrapper containing responsive sidebar and header.
*   `context/`: Global contexts (e.g., `AuthProvider.jsx` for active sessions, `ToastContext.jsx` for notification cues).
*   `pages/`: Full screen views mapped directly to application routing paths (e.g., `Dashboard.jsx`, `MeusAtivos.jsx`, `AtivoDetalhes.jsx`).
*   `services/`: Communication layer with the Django REST API.
    *   `api.js`: Base Axios client with JWT refresh token interceptors.
    *   `financeiro.js` & `investimentos.js`: Service functions for API routes.
*   `index.css`: Global styles, fonts (Outfit/Inter), and Tailwind CSS v4 custom theme definitions.

---

## 🎨 2. UX/UI & Visual Identity System

FreeCash implements a **SaaS Flat Premium** design system. All visual surfaces must look premium, modern, clean, and highly readable, avoiding complex multi-stop gradients or cluttered grid layouts.

### 🟢 Theme Colors
Colors are configured dynamically using CSS variables inside Tailwind v4. The default primary colors are:

| Element | HSL / CSS Value | Description |
| :--- | :--- | :--- |
| **Accent / Primary** | `#007acc` (`hsl(207, 100%, 40%)`) | Solid Technological Blue. Used for active tabs, main buttons, focus rings, sliders, and primary highlights. |
| **Light Background** | `#eeeeee` | Flat slate light grey. Never use heavy pure white grids. |
| **Light Foreground**| `#101010` | High-contrast dark charcoal for crisp readability in light mode. |
| **Dark Background**  | `#101010` | High-premium slate/chumbo flat dark. |
| **Dark Foreground** | `#cccccc` | Soft light grey text to minimize eye strain. |

### 🟢 Card & Wrapper Guidelines
*   Cards must never use saturated gradients or heavy glassmorphism filters under standard views.
*   Standard Card classes:
    ```html
    <div className="bg-card border border-border/40 shadow-sm text-card-foreground rounded-xl p-6">
      <!-- Content -->
    </div>
    ```
*   Spacing: Keep card layouts spacious. Use standard padding (`p-6` or `p-8` for larger containers) and generous vertical/horizontal margins (`space-y-6`, `gap-6`) to keep the design airy.

---

## 📊 3. Standardized `DataTable` Component Blueprint

To maintain a consistent, high-performance user experience, **every** data table or listing grid in FreeCash must be rendered using the standardized `DataTable` component (`components/ui/DataTable.jsx`).

### 🔹 3.1 Component Specifications & Properties
The `DataTable` handles client-side searching, sorting, pagination, and empty states automatically.

```javascript
import DataTable from '@/components/ui/DataTable';

const columns = [
  { 
    header: 'Ticker', 
    accessor: 'ticker', 
    sortable: true,
    render: (value, row) => <span className="font-semibold text-primary">{value}</span> 
  },
  { 
    header: 'Preço Médio', 
    accessor: 'preco_medio', 
    sortable: true,
    render: (value) => `R$ ${parseFloat(value).toFixed(2)}` 
  },
  // ...
];

<DataTable
  columns={columns}
  data={data}
  searchPlaceholder="Buscar ativos..."
  searchColumn="ticker"
  initialRowsPerPage={10}
/>
```

### 🔹 3.2 Key Rules for Table Layouts
*   **Search and Filter Integration**: Use the built-in `searchPlaceholder` and `searchColumn` properties instead of nesting redundant text filters.
*   **Actions Column**: Action buttons (edit, delete, view details) must be wrapped in a flex container inside an `Acoes` column, using micro-animations on hover.
*   **Performance Bounds**: Ensure pagination is always enabled (`initialRowsPerPage` defaults to 10 or 15) to maintain the target `<2s` rendering benchmark.

---

## 📈 4. Asset Details & Dynamic Modal Lifecycles (`AtivoDetalhes.jsx`)

When displaying rich historical charts, transactional history logbooks, or ANBIMA alocations for a specific asset, the application uses detailed screens or modals (e.g. `AtivoDetalhes.jsx`).

### 🔹 4.1 ApexCharts & Lifecycle Optimization
To prevent fatal React rendering errors such as `Uncaught TypeError: Cannot read properties of null (reading 'node')` during rapid page transitions or modal unmountings:

1.  **Conditional Render**: Ensure the chart `<Chart>` element is only mounted to the DOM once the query is resolved and data arrays are fully loaded.
    ```javascript
    {data?.labels?.length > 0 ? (
      <Chart options={chartOptions} series={chartSeries} type="area" />
    ) : (
      <div className="flex items-center justify-center h-[300px] text-muted-foreground">Carregando dados...</div>
    )}
    ```
2.  **Dynamic Keying (Remount)**: Force React to rebuild the chart instance from scratch instead of applying buggy SVG animation transitions on unmounted/stale DOM nodes.
    ```javascript
    <Chart key={`chart-${ativoId}-${periodo}`} options={chartOptions} series={chartSeries} type="bar" />
    ```
3.  **Flat Animations**: Disable ApexCharts SVG animations to increase page transition speed and prevent rendering race conditions in React 18/19 StrictMode.
    ```javascript
    const chartOptions = {
      chart: {
        animations: {
          enabled: false,
        },
      },
      // ...other options
    }
    ```

---

## ⚡ 5. React Query Integration Standards

### 🛡️ Preventing Context Parameter Leaks (CRITICAL)
When using the `useQuery` hook, **never** pass the fetch function directly if it accepts optional parameters. React Query will inject its internal execution context as arguments, which Axios serializes into query string parameters, causing `404 Not Found` routing errors or polluted API endpoints.

*   ❌ **Incorrect (Direct Reference)**:
    ```javascript
    const { data } = useQuery({
      queryKey: ['cartoes'],
      queryFn: fetchCartoes, // Passes QueryContext object as first parameter
    })
    ```
*   ✅ **Correct (Arrow Function Wrapping)**:
    ```javascript
    const { data } = useQuery({
      queryKey: ['cartoes'],
      queryFn: () => fetchCartoes(), // Sanitizes invocation, passing 0 arguments
    })
    ```

---

## 🔒 6. Security & Session Protocols

*   **Token Isolation**: Access tokens must be stored strictly in-memory (React component state/helper variable) and never written to `localStorage` or `sessionStorage` (preventing XSS exploitation).
*   **Automatic Session Refresh**: The service layer in `api.js` must implement an Axios interceptor to capture `401 Unauthorized` errors. It must perform a background refresh using `/api/token/refresh/` (which consumes the HttpOnly secure cookie) and retry the failed requests seamlessly without interrupting the user.
*   **Input Sanitization**: Always bind variables directly inside JSX bindings (`{value}`) instead of using unsafe direct HTML insertions (`dangerouslySetInnerHTML`), unless rendering explicitly sanitized HTML structures.
