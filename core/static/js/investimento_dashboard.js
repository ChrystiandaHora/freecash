document.addEventListener("DOMContentLoaded", () => {
    // Parse JSON data
    const allocationLabelsEl = document.getElementById("allocationLabels");
    const allocationValuesEl = document.getElementById("allocationValues");
    const categoryLabelsEl = document.getElementById("categoryLabels");
    const categoryValuesEl = document.getElementById("categoryValues");
    const performanceMonthlyEl = document.getElementById("performanceMonthly");
    const performanceYearlyEl = document.getElementById("performanceYearly");

    const allocationLabels = allocationLabelsEl ? JSON.parse(allocationLabelsEl.textContent || "[]") : [];
    const allocationValues = allocationValuesEl ? JSON.parse(allocationValuesEl.textContent || "[]").map((v) => Number(v) || 0) : [];
    const categoryLabels = categoryLabelsEl ? JSON.parse(categoryLabelsEl.textContent || "[]") : [];
    const categoryValues = categoryValuesEl ? JSON.parse(categoryValuesEl.textContent || "[]").map((v) => Number(v) || 0) : [];
    const performanceMonthly = performanceMonthlyEl ? JSON.parse(performanceMonthlyEl.textContent || "[]") : [];
    const performanceYearly = performanceYearlyEl ? JSON.parse(performanceYearlyEl.textContent || "[]") : [];

    // Theme detection
    const isDark = document.documentElement.classList.contains("dark");
    const textColor = isDark ? "#94a3b8" : "#64748b";

    // Chart colors
    const chartColors = [
        "#10b981",
        "#3b82f6",
        "#f59e0b",
        "#ef4444",
        "#8b5cf6",
        "#ec4899",
        "#14b8a6",
        "#f97316",
    ];
    const catColors = [
        "#6366f1",
        "#f43f5e",
        "#0ea5e9",
        "#84cc16",
        "#a855f7",
        "#22d3ee",
        "#eab308",
        "#fb923c",
        "#06b6d4",
        "#d946ef",
    ];

    // Set CSS variables for legend colors
    chartColors.forEach((color, i) => {
        document.documentElement.style.setProperty(`--chart-color-${i}`, color);
    });
    catColors.forEach((color, i) => {
        document.documentElement.style.setProperty(`--cat-color-${i}`, color);
    });

    // Currency formatter
    const brl = new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
    });

    // Allocation Donut Chart (Class)
    if (allocationLabels.length > 0 && document.getElementById("chartAllocation")) {
        const allocationChart = new ApexCharts(document.getElementById("chartAllocation"), {
            series: allocationValues,
            labels: allocationLabels,
            chart: {
                type: "donut",
                height: 220,
                fontFamily: "Inter, sans-serif",
            },
            colors: chartColors.slice(0, allocationLabels.length),
            plotOptions: {
                pie: {
                    donut: {
                        size: "70%",
                        labels: {
                            show: true,
                            name: { show: true, fontSize: "11px", color: textColor },
                            value: {
                                show: true,
                                fontSize: "14px",
                                fontWeight: "bold",
                                color: isDark ? "#fff" : "#1f2937",
                                formatter: (val) => brl.format(val),
                            },
                            total: {
                                show: true,
                                label: "Total",
                                fontSize: "11px",
                                color: textColor,
                                formatter: (w) =>
                                    brl.format(
                                        w.globals.seriesTotals.reduce((a, b) => a + b, 0),
                                    ),
                            },
                        },
                    },
                },
            },
            legend: { show: false },
            dataLabels: { enabled: false },
            stroke: { show: false },
            tooltip: {
                theme: isDark ? "dark" : "light",
                y: { formatter: (val) => brl.format(val) },
            },
        });
        allocationChart.render();
    }

    // Category Donut Chart
    if (categoryLabels.length > 0 && document.getElementById("chartCategory")) {
        const categoryChart = new ApexCharts(document.getElementById("chartCategory"), {
            series: categoryValues,
            labels: categoryLabels,
            chart: {
                type: "donut",
                height: 220,
                fontFamily: "Inter, sans-serif",
            },
            colors: catColors.slice(0, categoryLabels.length),
            plotOptions: {
                pie: {
                    donut: {
                        size: "70%",
                        labels: {
                            show: true,
                            name: { show: true, fontSize: "11px", color: textColor },
                            value: {
                                show: true,
                                fontSize: "14px",
                                fontWeight: "bold",
                                color: isDark ? "#fff" : "#1f2937",
                                formatter: (val) => brl.format(val),
                            },
                            total: {
                                show: true,
                                label: "Total",
                                fontSize: "11px",
                                color: textColor,
                                formatter: (w) =>
                                    brl.format(
                                        w.globals.seriesTotals.reduce((a, b) => a + b, 0),
                                    ),
                            },
                        },
                    },
                },
            },
            legend: { show: false },
            dataLabels: { enabled: false },
            stroke: { show: false },
            tooltip: {
                theme: isDark ? "dark" : "light",
                y: { formatter: (val) => brl.format(val) },
            },
        });
        categoryChart.render();
    }

    // Performance Monthly/Yearly Chart (Candlestick + Linha de Investimento)
    const performanceEl = document.getElementById("chartPerformance");
    if (performanceEl && (performanceMonthly.length > 0 || performanceYearly.length > 0)) {
        let mode = "monthly"; // monthly|yearly
        let range = 36; // points

        const sliceRange = (rows, r) => {
            if (!rows || rows.length === 0) return [];
            if (r === "all") return rows;
            const n = Number(r);
            if (!Number.isFinite(n) || n <= 0) return rows;
            return rows.slice(-n);
        };

        const getRows = () => {
            const rows = mode === "yearly" ? performanceYearly : performanceMonthly;
            return sliceRange(rows, range);
        };

        const toCandleData = (rows) => {
            return rows.map((r) => ({
                x: new Date(r.data + "T00:00:00").getTime(),
                y: r.ohlc,
            }));
        };

        const toInvestidoData = (rows) => {
            return rows.map((r) => ({
                x: new Date(r.data + "T00:00:00").getTime(),
                y: r.investido,
            }));
        };

        const performanceChart = new ApexCharts(performanceEl, {
            series: [
                {
                    name: "Patrimônio (OHLC)",
                    type: "candlestick",
                    data: toCandleData(getRows()),
                },
                {
                    name: "Valor Investido",
                    type: "line",
                    data: toInvestidoData(getRows()),
                },
            ],
            chart: {
                height: 280,
                type: "line", // Misto
                fontFamily: "Inter, sans-serif",
                toolbar: { show: false },
                zoom: { enabled: false },
            },
            colors: ["#10b981", "#3b82f6"],
            plotOptions: {
                candlestick: {
                    colors: {
                        upward: "#10b981",
                        downward: "#ef4444",
                    },
                    wick: { useFillColor: true },
                },
            },
            stroke: {
                width: [1, 3],
                curve: "smooth",
            },
            xaxis: {
                type: "datetime",
                labels: {
                    style: { colors: textColor, fontSize: "11px" },
                    datetimeUTC: false,
                },
                axisBorder: { show: false },
                axisTicks: { show: false },
            },
            yaxis: {
                labels: {
                    style: { colors: textColor, fontSize: "11px" },
                    formatter: (val) => brl.format(val),
                },
            },
            grid: {
                borderColor: isDark ? "#334155" : "#e5e7eb",
                strokeDashArray: 4,
            },
            tooltip: {
                theme: isDark ? "dark" : "light",
                shared: true,
                custom: function({ series, seriesIndex, dataPointIndex, w }) {
                    const ohlc = w.globals.initialSeries[0].data[dataPointIndex].y;
                    const investido = w.globals.initialSeries[1].data[dataPointIndex].y;
                    const date = new Date(w.globals.seriesX[0][dataPointIndex]).toLocaleDateString("pt-BR", { month: "short", year: "numeric" });
                    
                    const lucro = ohlc[3] - investido;
                    const lucroPerc = investido > 0 ? (lucro / investido) * 100 : 0;
                    const lucroColor = lucro >= 0 ? "text-emerald-500" : "text-red-500";

                    return `
                        <div class="p-3 bg-white dark:bg-slate-800 border border-gray-100 dark:border-slate-700 rounded-lg shadow-xl min-w-[200px]">
                            <div class="text-xs font-bold text-gray-400 mb-2 uppercase tracking-wider">${date}</div>
                            <div class="space-y-2">
                                <div class="flex justify-between items-center gap-4">
                                    <span class="text-xs text-gray-500 dark:text-slate-400">Abertura:</span>
                                    <span class="text-xs font-mono font-bold">${brl.format(ohlc[0])}</span>
                                </div>
                                <div class="flex justify-between items-center gap-4">
                                    <span class="text-xs text-gray-500 dark:text-slate-400 text-emerald-500">Máxima:</span>
                                    <span class="text-xs font-mono font-bold">${brl.format(ohlc[1])}</span>
                                </div>
                                <div class="flex justify-between items-center gap-4">
                                    <span class="text-xs text-gray-500 dark:text-slate-400 text-red-500">Mínima:</span>
                                    <span class="text-xs font-mono font-bold">${brl.format(ohlc[2])}</span>
                                </div>
                                <div class="flex justify-between items-center gap-4">
                                    <span class="text-xs text-gray-500 dark:text-slate-400">Fechamento:</span>
                                    <span class="text-xs font-mono font-bold">${brl.format(ohlc[3])}</span>
                                </div>
                                <div class="pt-2 mt-2 border-t border-gray-100 dark:border-slate-700">
                                    <div class="flex justify-between items-center gap-4">
                                        <span class="text-xs text-gray-500 dark:text-slate-400">Total Investido:</span>
                                        <span class="text-xs font-mono font-bold text-blue-500">${brl.format(investido)}</span>
                                    </div>
                                    <div class="flex justify-between items-center gap-4 mt-1">
                                        <span class="text-xs text-gray-500 dark:text-slate-400">Resultado:</span>
                                        <span class="text-xs font-mono font-bold ${lucroColor}">${brl.format(lucro)} (${lucroPerc.toFixed(1)}%)</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }
            },
        });

        performanceChart.render();

        const refresh = () => {
            const rows = getRows();
            performanceChart.updateSeries([
                {
                    name: "Patrimônio (OHLC)",
                    type: "candlestick",
                    data: toCandleData(rows),
                },
                {
                    name: "Valor Investido",
                    type: "line",
                    data: toInvestidoData(rows),
                },
            ], true);
        };

        // Wire buttons
        document.querySelectorAll(".js-performance-mode").forEach((btn) => {
            btn.addEventListener("click", () => {
                mode = btn.dataset.mode || "monthly";
                refresh();
            });
        });
        document.querySelectorAll(".js-performance-range").forEach((btn) => {
            btn.addEventListener("click", () => {
                range = btn.dataset.range === "all" ? "all" : Number(btn.dataset.range || 36);
                refresh();
            });
        });
    }
});
