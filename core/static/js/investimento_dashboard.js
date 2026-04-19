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

    // Performance Monthly/Yearly Chart (Rentabilidade Isolada)
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

        const toSeriesData = (rows) => {
            // Calcula a rentabilidade isolada do período (Delta)
            return rows.map((r, i) => {
                const current = Number(r.rentabilidade_percentual) || 0;
                const previous = i > 0 ? (Number(rows[i - 1].rentabilidade_percentual) || 0) : 0;
                
                return {
                    x: new Date(r.data + "T00:00:00").getTime(),
                    y: parseFloat((current - previous).toFixed(2)),
                };
            });
        };

        const performanceChart = new ApexCharts(performanceEl, {
            series: [
                {
                    name: "Rentabilidade",
                    data: toSeriesData(getRows()),
                },
            ],
            chart: {
                type: "bar",
                height: 280,
                fontFamily: "Inter, sans-serif",
                toolbar: { show: false },
                zoom: { enabled: false },
            },
            plotOptions: {
                bar: {
                    colors: {
                        ranges: [
                            { from: -1000, to: -0.01, color: "#ef4444" }, // Red for negative
                            { from: 0, to: 1000, color: "#10b981" }       // Green for positive
                        ]
                    },
                    columnWidth: "60%",
                    borderRadius: 4,
                }
            },
            dataLabels: { enabled: false },
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
                    formatter: (val) => val.toFixed(2) + "%",
                },
            },
            grid: {
                borderColor: isDark ? "#334155" : "#e5e7eb",
                strokeDashArray: 4,
            },
            tooltip: {
                theme: isDark ? "dark" : "light",
                x: { format: mode === "yearly" ? "yyyy" : "MMM yyyy" },
                y: {
                    formatter: (val) => (val > 0 ? "+" : "") + val.toFixed(2) + "%",
                    title: { formatter: () => "Rentabilidade: " }
                }
            },
        });

        performanceChart.render();

        const refresh = () => {
            performanceChart.updateSeries([
                {
                    name: "Rentabilidade",
                    data: toSeriesData(getRows()),
                },
            ], true);
            
            performanceChart.updateOptions({
                tooltip: {
                    x: { format: mode === "yearly" ? "yyyy" : "MMM yyyy" }
                }
            });
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
