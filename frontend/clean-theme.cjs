const fs = require('fs');
const path = require('path');

const files = [
  path.join(__dirname, 'src', 'pages', 'Dashboard.jsx'),
  path.join(__dirname, 'src', 'pages', 'Investimentos.jsx')
];

files.forEach(file => {
  if (fs.existsSync(file)) {
    let content = fs.readFileSync(file, 'utf8');

    // Remove gradients
    content = content.replace(/bg-gradient-to-r from-emerald-500 to-teal-400 bg-clip-text text-transparent/g, 'text-primary font-extrabold');
    content = content.replace(/bg-gradient-to-r from-teal-500 to-emerald-500/g, 'bg-primary');
    content = content.replace(/bg-gradient-to-tr from-emerald-500 to-teal-500/g, 'bg-primary');
    
    // Replace emerald with primary
    content = content.replace(/text-emerald-500/g, 'text-primary');
    content = content.replace(/text-emerald-600/g, 'text-primary');
    content = content.replace(/text-emerald-400/g, 'text-primary/80');
    content = content.replace(/bg-emerald-500\/10/g, 'bg-primary/10');
    content = content.replace(/bg-emerald-500\/20/g, 'bg-primary/20');
    content = content.replace(/bg-emerald-500\/5/g, 'bg-primary/5');
    content = content.replace(/bg-emerald-500/g, 'bg-primary');
    content = content.replace(/border-emerald-500\/20/g, 'border-primary/20');
    content = content.replace(/border-emerald-500\/10/g, 'border-primary/10');
    content = content.replace(/border-emerald-500/g, 'border-primary');

    // Fix ApexCharts key in Investimentos.jsx
    if (file.includes('Investimentos.jsx')) {
      content = content.replace(
        /<Chart\s*options=\{donutChartOptions\}\s*series=\{donutChartSeries\}\s*type="donut"\s*width=\{320\}\s*\/>/g,
        '<Chart key={`donut-${donutChartSeries.join("-")}`} options={donutChartOptions} series={donutChartSeries} type="donut" width={320} />'
      );
    }

    fs.writeFileSync(file, content, 'utf8');
    console.log(`Updated ${path.basename(file)}`);
  }
});
