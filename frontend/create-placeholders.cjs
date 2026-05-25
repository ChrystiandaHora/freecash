const fs = require('fs');
const path = require('path');

const pagesDir = path.join(__dirname, 'src', 'pages');

const pages = [
  { name: 'Relatorios', title: 'Relatórios' },
  { name: 'ContasPagar', title: 'Contas a Pagar' },
  { name: 'PipelineKanban', title: 'Pipeline Kanban' },
  { name: 'MeusCartoes', title: 'Meus Cartões' },
  { name: 'Receitas', title: 'Receitas' },
  { name: 'Transacoes', title: 'Transações' },
  { name: 'AtivosBalanceamento', title: 'Balanceamento de Ativos' },
  { name: 'AtivosHistorico', title: 'Histórico de Investimentos' },
  { name: 'AtivosClasses', title: 'Classes de Ativos' },
  { name: 'FerramentasImportar', title: 'Importar Dados' },
  { name: 'FerramentasConciliacao', title: 'Conciliação Bancária' },
  { name: 'FerramentasBackup', title: 'Backup de Dados' },
  { name: 'AjustesPagamentos', title: 'Formas de Pagamento' },
];

if (!fs.existsSync(pagesDir)) {
  fs.mkdirSync(pagesDir, { recursive: true });
}

pages.forEach((page) => {
  const filePath = path.join(pagesDir, `${page.name}.jsx`);
  const content = `import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card';
import { Wrench } from 'lucide-react';

export default function ${page.name}() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 to-slate-700 dark:from-white dark:to-slate-300 bg-clip-text text-transparent">
          ${page.title}
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Página em desenvolvimento (Placeholder)
        </p>
      </div>

      <Card className="glass">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-900 flex items-center justify-center border border-slate-200/50 dark:border-slate-800/50 mb-4">
            <Wrench className="h-8 w-8 text-slate-400" />
          </div>
          <CardTitle className="text-xl">Em Construção</CardTitle>
          <CardDescription>
            Esta página (${page.title}) será conectada às novas APIs do backend em breve.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex justify-center pt-6 pb-12">
          <p className="text-sm text-slate-500 dark:text-slate-500 text-center max-w-md">
            A estrutura visual do menu lateral já suporta esta rota, mantendo o roteamento limpo para quando a funcionalidade estiver disponível.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
`;
  
  if (!fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`Created ${page.name}.jsx`);
  } else {
    console.log(`Skipped ${page.name}.jsx (already exists)`);
  }
});

console.log('Done!');
