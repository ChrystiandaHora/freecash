document.addEventListener("DOMContentLoaded", () => {
    // Parse JSON data
    const allocationLabelsEl = document.getElementById("allocationLabels");
    const allocationValuesEl = document.getElementById("allocationValues");
    const categoryLabelsEl = document.getElementById("categoryLabels");
    const categoryValuesEl = document.getElementById("categoryValues");

    const allocationLabels = allocationLabelsEl ? JSON.parse(allocationLabelsEl.textContent || "[]") : [];
    const allocationValues = allocationValuesEl ? JSON.parse(allocationValuesEl.textContent || "[]").map((v) => Number(v) || 0) : [];
    const categoryLabels = categoryLabelsEl ? JSON.parse(categoryLabelsEl.textContent || "[]") : [];
    const categoryValues = categoryValuesEl ? JSON.parse(categoryValuesEl.textContent || "[]").map((v) => Number(v) || 0) : [];

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
});
