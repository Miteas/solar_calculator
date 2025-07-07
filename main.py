import numpy as np
import pandas as pd
from fasthtml.common import *
from monsterui.all import *

from config import TEXTS

tariff_df = pd.read_csv("data/tariff_df.csv", index_col=0, parse_dates=True)
merged = pd.read_csv(
    "data/merged_solar_consumption.csv", index_col=0, parse_dates=True
)

# Round merged solar to 2dp
merged["solar"] = merged["solar"].round(2)

monster_hdrs = Theme.green.headers(radii="sm", font="sm", apex_charts=True)
custom_font_hdrs = [
    Link(rel="stylesheet", href="..."), # Your font link
    Style("""
        /* This base rule is still good */
        body {
            font-family: 'Forum', serif !important;
            font-size: clamp(14px, 2.5vw, 18px);
        }

        /* --- UNIFIED STYLING RULES --- */
        /* These rules now apply to H3/P on your main page AND the
           h1/h2/p from markdown, because they are all inside .prose */
        .prose h1 { font-size: clamp(24px, 4vw, 36px); }
        .prose h2 { font-size: clamp(20px, 3.5vw, 28px); }
        .prose h3 { font-size: clamp(18px, 3vw, 24px); }
        .prose p { font-size: clamp(14px, 2.5vw, 18px); }
        .prose ul, .prose ol { font-size: clamp(14px, 2.5vw, 18px); }
        

    """)
]

hdrs = monster_hdrs + custom_font_hdrs


app, rt = fast_app(hdrs=hdrs, live=True)


def calculate_costs_detailed(
    consumption,
    solar_gen,
    import_rates,
    export_rates=None,
    array_size_kw=1,
    cost_per_kw=1250,
    export_rate=0,
):
    # Annual calculations
    export_rate_float = float(export_rate)

    cost_wo_solar_annual = (consumption * import_rates).sum()
    consumption_w_solar = (consumption - solar_gen).clip(lower=0)
    cost_w_solar_annual = (consumption_w_solar * import_rates).sum()

    # Handle export revenue
    export_revenue_annual = 0
    export = (solar_gen - consumption).clip(lower=0)

    if export_rates is not None:
        export_revenue_annual = (export * export_rates).sum()
        cost_w_solar_annual -= export_revenue_annual
    elif export_rate_float != 0:
        export_revenue_annual = (export * export_rate_float).sum()
        cost_w_solar_annual -= export_revenue_annual

    # Monthly breakdown
    monthly_without = (consumption * import_rates).resample("ME").sum()
    monthly_with = (consumption_w_solar * import_rates).resample("ME").sum()
    monthly_export_revenue = pd.Series(0, index=monthly_without.index)

    if export_rates is not None:
        monthly_export_revenue = (export * export_rates).resample("ME").sum()
        monthly_with -= monthly_export_revenue
    elif export_rate_float != 0:
        monthly_export_revenue = (export * export_rate_float).resample("ME").sum()
        monthly_with -= monthly_export_revenue

    # Monthly savings
    monthly_savings = monthly_without - monthly_with

    # Savings and payback
    annual_savings = round(cost_wo_solar_annual - cost_w_solar_annual, 2)
    total_system_cost = round(array_size_kw * cost_per_kw, 2)
    payback_years = (
        total_system_cost / annual_savings if annual_savings > 0 else float("inf")
    )

    return {
        "cost_wo_solar_annual": round(cost_wo_solar_annual, 2),
        "cost_w_solar_annual": round(cost_w_solar_annual, 2),
        "annual_savings": annual_savings,
        "monthly_without": round(monthly_without, 2),
        "monthly_with": round(monthly_with, 2),
        "monthly_export_revenue": round(monthly_export_revenue, 2),
        "monthly_savings": round(monthly_savings, 2),
        "export_revenue_annual": round(export_revenue_annual, 2),
        "payback_years": (
            round(payback_years, 2) if payback_years != float("inf") else payback_years
        ),
        "total_system_cost": total_system_cost,
        "solar_gen": solar_gen,
        "consumption": consumption,
        "export": export,
    }


@rt
def calculate(array_size: str, tariff: str, export_rate: str = "0"):
    size_kw = float(array_size.replace("kW", ""))
    solar_gen = merged["solar"] * size_kw

    if tariff == "Agile 2024 Import":
        results = calculate_costs_detailed(
            merged["Consumption_kW"],
            solar_gen,
            tariff_df["Agile 2024 Import"],
            tariff_df["Agile 2024 Export"],
            size_kw,
        )
    else:
        results = calculate_costs_detailed(
            merged["Consumption_kW"],
            solar_gen,
            tariff_df[tariff],
            array_size_kw=size_kw,
            export_rate=export_rate,
        )

    # Simple comparison bar chart
    comparison_chart = ApexChart(
        opts={
            "chart": {"type": "bar", "height": 350},
            "theme": {"palette": "palette5"},
            "series": [
                {
                    "name": "Annual Cost",
                    "data": [
                        results["cost_wo_solar_annual"],
                        results["cost_w_solar_annual"],
                    ],
                }
            ],
            "xaxis": {"categories": ["Without Solar", "With Solar"]},
            "title": {"text": "Annual Energy Cost Comparison"},
            "yaxis": {"title": {"text": "Cost (£)"}},
        }
    )

    # Monthly breakdown chart
    monthly_chart = ApexChart(
        opts={
            "chart": {"type": "bar", "height": 800},
            "plotOptions": {"bar": {"horizontal": True}},
            "theme": {"palette": "palette5"},
            "series": [
                {"name": "Without Solar", "data": results["monthly_without"].tolist()},
                {"name": "With Solar", "data": results["monthly_with"].tolist()},
            ],
            "xaxis": {
                "categories": [
                    month.strftime("%b") for month in results["monthly_without"].index
                ]
            },
            "title": {"text": "Monthly Cost Breakdown"},
            "yaxis": {"title": {"text": "Cost (£)"}},
        }
    )

    # Solar Generation vs Consumption chart
    monthly_solar = results["solar_gen"].resample("ME").sum()
    monthly_consumption = results["consumption"].resample("ME").sum()

    solar_vs_consumption_chart = ApexChart(
        opts={
            "chart": {"type": "line", "height": 400},
            "theme": {"palette": "palette5"},
            "series": [
                {
                    "name": "Solar Generation",
                    "data": [round(float(x), 2) for x in monthly_solar.tolist()],
                },
                {
                    "name": "Consumption",
                    "data": [round(float(x), 2) for x in monthly_consumption.tolist()],
                },
            ],
            "xaxis": {
                "categories": [month.strftime("%b") for month in monthly_solar.index]
            },
            "title": {"text": "Monthly Solar Generation vs Consumption"},
            "yaxis": {"title": {"text": "Energy (kWh)"}},
            "stroke": {"curve": "smooth"},
        }
    )

    # Monthly Export Revenue vs Savings chart
    export_revenue_chart = ApexChart(
        opts={
            "chart": {"type": "bar", "height": 400},
            "theme": {"palette": "palette4"},
            "series": [
                {
                    "name": "Export Revenue",
                    "data": results["monthly_export_revenue"].tolist(),
                },
                {
                    "name": "Total Monthly Savings",
                    "data": results["monthly_savings"].tolist(),
                },
            ],
            "xaxis": {
                "categories": [
                    month.strftime("%b")
                    for month in results["monthly_export_revenue"].index
                ]
            },
            "title": {"text": "Monthly Export Revenue vs Total Savings"},
            "yaxis": {"title": {"text": "Amount (£)"}},
        }
    )

    # 10-Year Cumulative Savings Projection
    years = list(range(1, 11))
    cumulative_savings = [round(results["annual_savings"] * year, 2) for year in years]
    system_cost_line = [round(results["total_system_cost"], 2)] * 10

    payback_point = []
    payback_years = results["payback_years"]
    if payback_years != float("inf") and payback_years <= 10:
        payback_point = [
            {
                "x": f"Year {int(payback_years)}",
                "y": results["total_system_cost"],
                "marker": {"size": 8, "fillColor": "#FF4560"},
                "label": {
                    "text": f"Payback: {payback_years:.1f} years",
                    "style": {"background": "#FF4560", "color": "#fff"},
                },
            }
        ]

    cumulative_chart = ApexChart(
        opts={
            "chart": {"type": "line", "height": 400},
            "theme": {"palette": "palette4"},
            "series": [
                {"name": "Cumulative Savings", "data": cumulative_savings},
                {"name": "System Cost", "data": system_cost_line},
            ],
            "xaxis": {
                "categories": [f"Year {year}" for year in years],
                "title": {"text": "Years"},
            },
            "title": {"text": "10-Year Cumulative Savings Projection"},
            "yaxis": {"title": {"text": "Amount (£)"}},
            "stroke": {"curve": "smooth"},
            "annotations": {"points": payback_point},
        }
    )

    def StatCard(title, value, color="primary"):
        "A card with a statistic that will be placed in the responsive grid."
        return Card(P(title, cls=TextPresets.muted_sm), H3(value, cls=f"text-{color}"))

    # Create a list of the data for the cards
    stats_data = [
        ("Cost without solar", f"£{results['cost_wo_solar_annual']:.2f}", "blue-600"),
        ("Cost of solar install", f"£{results['total_system_cost']:.2f}", "blue-600"),
        ("Cost with solar", f"£{results['cost_w_solar_annual']:.2f}", "green-600"),
        ("Annual savings", f"£{results['annual_savings']:.2f}", "purple-600"),
        ("Export Revenue", f"£{results['export_revenue_annual']:.2f}", "purple-600"),
        ("Payback time", f"{results['payback_years']:.1f} years", "amber-600"),
    ]

    # Create the list of card components
    stat_cards = [StatCard(*data) for data in stats_data]

    # Use a responsive Grid instead of DivHStacked
    stats_grid = Grid(
        *stat_cards,
        cols_sm=2,  
        cols_md=3,  
        cols_lg=6,
        gap=4, 
        cls="mt-8",  
    )

    @rt
    def overview():
        return Div(
            Div(
                H3("Annual Overview", cls="text-xl font-bold mb-2"),
                P(TEXTS["annual_overview"], cls="text-gray-600 mb-8"),
                Hr(cls="border-gray-300"),
            ),
            comparison_chart,
            cls="mt-8",
        )

    @rt
    def monthly():
        return Div(
            Div(
                H3("Monthly Breakdown", cls="text-xl font-bold mb-2"),
                P(TEXTS["monthly_breakdown"], cls="text-gray-600 mb-8"),
                Hr(cls="border-gray-300"),
            ),
            monthly_chart,
            cls="mt-8",
        )

    @rt
    def solar_vs_consumption():
        return Div(
            Div(
                H3("Solar Generation vs Consumption", cls="text-xl font-bold mb-2"),
                P(TEXTS["solar_vs_consumption"], cls="text-gray-600 mb-8"),
                Hr(cls="border-gray-300"),
            ),
            solar_vs_consumption_chart,
            cls="mt-8",
        )

    @rt
    def export_savings():
        return Div(
            Div(
                H3("Export Revenue vs Total Savings", cls="text-xl font-bold mb-2"),
                P(TEXTS["export_savings"], cls="text-gray-600 mb-8"),
                Hr(cls="border-gray-300"),
            ),
            export_revenue_chart,
            cls="mt-8",
        )

    @rt
    def cumulative_projection():
        return Div(
            Div(
                H3("10-Year Cumulative Savings Projection", cls="text-xl font-bold mb-2"),
                P(TEXTS["cumulative_projection"], cls="text-gray-600 mb-4"),
                Hr(cls="border-gray-300"),
            ),
            cumulative_chart,
            cls="mt-8",
        )

    tabs = Div(
        Button(
            "Monthly Breakdown",
            hx_get=monthly,
            hx_target="#tab-content",
            hx_swap="innerHTML scroll:none",  
            cls="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded",
        ),
        Button(
            "Solar vs Consumption",
            hx_get=solar_vs_consumption,
            hx_target="#tab-content",
            hx_swap="innerHTML scroll:none",  
            cls="bg-yellow-500 hover:bg-yellow-600 text-white px-4 py-2 rounded",
        ),
        Button(
            "Export vs Savings",
            hx_get=export_savings,
            hx_target="#tab-content",
            hx_swap="innerHTML scroll:none",  
            cls="bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded",
        ),
        Button(
            "10-Year Projection",
            hx_get=cumulative_projection,
            hx_target="#tab-content",
            hx_swap="innerHTML scroll:none",  
            cls="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded",
        ),
        cls="flex justify-center space-x-2 flex-wrap gap-2",
    )

    return Div(
        stats_grid,
        Div(comparison_chart, cls="mt-8"),
        Div(
            tabs,
            Div(monthly(), id="tab-content", cls="mt-8 min-h-[600px]"),
            cls="mt-8"
        )
    )




@rt
def index():
    array_sizes = [f"{i / 1000:.1f}kW" for i in range(2000, 8001, 400)]
    tariffs = [
        col for col in tariff_df.columns if not col.split()[-1].lower() == "export"
    ]
    export_rate_options = [f"{i/100:.2f}" for i in range(16)]

    default_array_size = "4.0kW"
    default_tariff = "Price Cap 2024"
    default_export_rate = "0.04"


    initial_results = calculate(
        array_size=default_array_size,
        tariff=default_tariff,
        export_rate=default_export_rate,
    )

    return (
        DivCentered(H2("Solar Install Payback Calculator"), cls="mt-8"),
        DividerLine(lwidth=2, y_space=4),
        DivCentered(P(TEXTS["intro"]), cls="prose container mx-auto py-2 px-4 sm:px-6 lg:px-8"),
        DividerLine(lwidth=2, y_space=8),
        Container(
            Form(id="calc-form")(
                Card(
                    DivCentered(H3("Solar System Configuration")),
                    Grid(
                        LabelSelect(
                            map(Option, array_sizes),
                            label="Array Size",
                            name="array_size",
                            value=default_array_size,
                            hx_trigger="change",
                            hx_post=calculate,
                            hx_target="#results",
                            hx_include="#calc-form",
                        ),
                        LabelSelect(
                            map(Option, tariffs),
                            label="Tariffs",
                            name="tariff",
                            value=default_tariff, 
                            hx_trigger="change",
                            hx_post=calculate,
                            hx_target="#results",
                            hx_include="#calc-form",
                        ),
                        cols=2,
                    ),
                    LabelSelect(
                        map(Option, export_rate_options),
                        label="Export Rate (£/kWh)",
                        name="export_rate",
                        value=default_export_rate,
                        hx_trigger="change",
                        hx_post=calculate,
                        hx_target="#results",
                        hx_include="#calc-form",
                    ),
                ),
            ),

            Div(initial_results, id="results"),
            cls="space-y-4",
        ),
    )


serve()