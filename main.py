from fasthtml.common import *
from monsterui.all import *
import pandas as pd
import numpy as np



tariff_df = pd.read_csv('data/tariff_df.csv', index_col=0, parse_dates=True)
merged = pd.read_csv('data/merged_solar_consumption.csv', index_col=0, parse_dates=True)


#round merged solar to 2dp
merged['solar'] = merged['solar'].round(2)

app, rt = fast_app(hdrs=Theme.green.headers(apex_charts=True, radii='lg', shadows='lg', font=' WDXL Lubrifont SC'))

def calculate_costs_detailed(consumption, solar_gen, import_rates, export_rates=None, array_size_kw=1, cost_per_kw=1250, export_rate=0):
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
    monthly_without = (consumption * import_rates).resample('ME').sum()
    monthly_with = (consumption_w_solar * import_rates).resample('ME').sum()
    monthly_export_revenue = pd.Series(0, index=monthly_without.index)
    
    if export_rates is not None:
        monthly_export_revenue = (export * export_rates).resample('ME').sum()
        monthly_with -= monthly_export_revenue
    elif export_rate_float != 0:
        monthly_export_revenue = (export * export_rate_float).resample('ME').sum()
        monthly_with -= monthly_export_revenue
    
    # Monthly savings
    monthly_savings = monthly_without - monthly_with
    
    # Savings and payback
    annual_savings = round(cost_wo_solar_annual - cost_w_solar_annual, 2)
    total_system_cost = round(array_size_kw * cost_per_kw, 2)
    payback_years = total_system_cost / annual_savings if annual_savings > 0 else float('inf')
    
    return {
        'cost_wo_solar_annual': round(cost_wo_solar_annual, 2),
        'cost_w_solar_annual': round(cost_w_solar_annual, 2),
        'annual_savings': round(annual_savings, 2),
        'monthly_without': round(monthly_without, 2),
        'monthly_with': round(monthly_with, 2),
        'monthly_export_revenue': round(monthly_export_revenue, 2),
        'monthly_savings': round(monthly_savings, 2),
        'export_revenue_annual': round(export_revenue_annual, 2),
        'payback_years': round(payback_years, 2) if payback_years != float('inf') else payback_years,
        'total_system_cost': round(total_system_cost, 2),
        'solar_gen': solar_gen,
        'consumption': consumption,
        'export': export
    }

@rt
def calculate(array_size: str, tariff: str, export_rate: str = "0"):  
    size_kw = float(array_size.replace('kW', ''))
    solar_gen = merged['solar'] * size_kw
    
    if tariff == "Agile 2024 Import":
        results = calculate_costs_detailed(
            merged['Consumption_kW'], 
            solar_gen, 
            tariff_df['Agile 2024 Import'], 
            tariff_df['Agile 2024 Export'],
            size_kw
        )
    else:
        results = calculate_costs_detailed(
            merged['Consumption_kW'], 
            solar_gen, 
            tariff_df[tariff],
            array_size_kw=size_kw,
            export_rate=export_rate
        )
    
    # Simple comparison bar chart
    comparison_chart = ApexChart(
        opts={
            "chart": {"type": "bar", "height": 350},
            "theme": {"palette": "palette5"},
            "series": [{
                "name": "Annual Cost",
                "data": [results['cost_wo_solar_annual'], results['cost_w_solar_annual']]
            }],
            "xaxis": {"categories": ["Without Solar", "With Solar"]},
            "title": {"text": "Annual Energy Cost Comparison"},
            "yaxis": {"title": {"text": "Cost (£)"}}
        }
    )
    
    # Monthly breakdown chart
    monthly_chart = ApexChart(
        opts={
            "chart": {"type": "bar", "height": 800},
            "plotOptions": {"bar": {"horizontal": True}},
            "theme": {"palette": "palette5"},
            "series": [
                {
                    "name": "Without Solar",
                    "data": results['monthly_without'].tolist()
                },
                {
                    "name": "With Solar", 
                    "data": results['monthly_with'].tolist()
                }
            ],
            "xaxis": {
                "categories": [month.strftime('%b') for month in results['monthly_without'].index]
            },
            "title": {"text": "Monthly Cost Breakdown"},
            "yaxis": {"title": {"text": "Cost (£)"}}
        }
    )
    
    # Solar Generation vs Consumption chart
    monthly_solar = results['solar_gen'].resample('ME').sum()
    monthly_consumption = results['consumption'].resample('ME').sum()
    
    solar_vs_consumption_chart = ApexChart(
        opts={
            "chart": {"type": "line", "height": 400},
            "theme": {"palette": "palette5"},
            "series": [
                {
                    "name": "Solar Generation",
                    "data": [round(float(x), 2) for x in monthly_solar.tolist()]
                },
                {
                    "name": "Consumption",
                    
                    "data": [round(float(x), 2) for x in monthly_consumption.tolist()]
                }
            ],
            "xaxis": {
                "categories": [month.strftime('%b') for month in monthly_solar.index]
            },
            "title": {"text": "Monthly Solar Generation vs Consumption"},
            "yaxis": {"title": {"text": "Energy (kWh)"}},
            "stroke": {"curve": "smooth"}
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
                    "data": results['monthly_export_revenue'].tolist()
                },
                {
                    "name": "Total Monthly Savings",
                    "data": results['monthly_savings'].tolist()
                }
            ],
            "xaxis": {
                "categories": [month.strftime('%b') for month in results['monthly_export_revenue'].index]
            },
            "title": {"text": "Monthly Export Revenue vs Total Savings"},
            "yaxis": {"title": {"text": "Amount (£)"}}
        }
    )
    
    # 10-Year Cumulative Savings Projection
    years = list(range(1, 11))
    cumulative_savings = [round(results['annual_savings'] * year, 2) for year in years]
    system_cost_line = [round(results['total_system_cost'], 2)] * 10
    
    cumulative_chart = ApexChart(
        opts={
            "chart": {"type": "line", "height": 400},
            "theme": {"palette": "palette4"},
            "series": [
                {
                    "name": "Cumulative Savings",
                    "data": cumulative_savings
                },
                {
                    "name": "System Cost",
                    "data": system_cost_line
                }
            ],
            "xaxis": {
                "categories": [f"Year {year}" for year in years],
                "title": {"text": "Years"}
            },
            "title": {"text": "10-Year Cumulative Savings Projection"},
            "yaxis": {"title": {"text": "Amount (£)"}},
            "stroke": {"curve": "smooth"},
            "annotations": {
                "points": [{
                    "x": f"Year {int(results['payback_years'])}" if results['payback_years'] != float('inf') else "Year 10",
                    "y": results['total_system_cost'],
                    "marker": {"size": 8, "fillColor": "#FF4560"},
                    "label": {
                        "text": f"Payback: {results['payback_years']:.1f} years",
                        "style": {"background": "#FF4560", "color": "#fff"}
                    }
                }] if results['payback_years'] != float('inf') and results['payback_years'] <= 10 else []
            }
        }
    )

    def StatCard(title, value, color='primary'):
        "A card with a statistics. Since there is no row/col span class it will take up 1 slot"
        return Card(P(title, cls=TextPresets.muted_sm), H3(value, cls=f'text-{color}'))

    stats = [DivHStacked(StatCard(*data) for data in [
        ("Cost without solar", f"£{results['cost_wo_solar_annual']:.2f}", "blue-600"),
        ("Cost of solar install", f"£{results['total_system_cost']:.2f}", "blue-600"),
        ("Cost with solar", f"£{results['cost_w_solar_annual']:.2f}", "green-600"),
        ("Annual savings", f"£{results['annual_savings']:.2f}", "purple-600"),
        ("Export Revenue", f"£{results['export_revenue_annual']:.2f}", "purple-600"),
        ("Payback time", f"{results['payback_years']:.1f} years", "amber-600")
    ])]


    @rt
    def overview():
        return Div(
            Div(
                H3("Annual Overview", cls="text-xl font-bold mb-2"),
                P(annual_overview_text, cls="text-gray-600 mb-8"),
                Hr(cls="border-gray-300")
            ),
            comparison_chart, 
            cls="mt-8"
        )

    @rt  
    def monthly():
        return Div(
            Div(
                H3("Monthly Breakdown", cls="text-xl font-bold mb-2"),
                P(monthly_breakdown_text, cls="text-gray-600 mb-8"),
                Hr(cls="border-gray-300")
            ),
            monthly_chart, 
            cls="mt-8"
        )

    @rt
    def solar_vs_consumption():
        return Div(
            Div(
                H3("Solar Generation vs Consumption", cls="text-xl font-bold mb-2"),
                P(solar_vs_consumption_text, cls="text-gray-600 mb-8"),
                Hr(cls="border-gray-300")
            ),
            solar_vs_consumption_chart, 
            cls="mt-8"
        )
    
    @rt
    def export_savings():
        return Div(
            Div(
                H3("Export Revenue vs Total Savings", cls="text-xl font-bold mb-2"),
                P(export_savings_text, cls="text-gray-600 mb-8"),
                Hr(cls="border-gray-300")
            ),
            export_revenue_chart, 
            cls="mt-8"
        )
    
    @rt
    def cumulative_projection():
        return Div(
            Div(
                H3("10-Year Cumulative Savings Projection", cls="text-xl font-bold mb-2"),
                P(cumulative_projection_text, cls="text-gray-600 mb-4"),
                Hr(cls="border-gray-300")
            ),
            cumulative_chart, 
            cls="mt-8"
        )


    tabs = Div(
        #Button("Annual Overview", hx_get=overview, hx_trigger="change, click from:button"  hx_target="#tab-content", cls="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded"),
        Button("Monthly Breakdown", hx_get=monthly, hx_target="#tab-content", cls="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded"),
        Button("Solar vs Consumption", hx_get=solar_vs_consumption, hx_target="#tab-content", cls="bg-yellow-500 hover:bg-yellow-600 text-white px-4 py-2 rounded"),
        Button("Export vs Savings", hx_get=export_savings, hx_target="#tab-content", cls="bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded"),
        Button("10-Year Projection", hx_get=cumulative_projection, hx_target="#tab-content", cls="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded"),
        cls="flex justify-center space-x-2 flex-wrap gap-2"
    )
    
    return Div(
        DivVStacked(*stats, cls="mt-8"),  # Stats always visible
        Div(comparison_chart, cls="mt-8"),
        Div(tabs, Div(id="tab-content", cls="mt-8"), cls="mt-8")
    )

@rt
def index():
    array_sizes = [f"{i/1000:.1f}kW" for i in range(2000, 8001, 400)]
    tariffs = [col for col in tariff_df.columns if not (col.split()[-1].lower() == 'export')]
    
    return (
        DivCentered(H2("Solar Install Payback Calculator"), cls="mt-8"),
        DividerLine(lwidth=2, y_space=4),
        DivCentered(P(intro_text), cls="mt-4 px-4"),
        DividerLine(lwidth=2, y_space=8),
        

        
        Container(
            Form(hx_post=calculate, hx_target="#results")(
                Card(
                    DivCentered(H3("Solar System Configuration")),
                    Grid(
                        LabelSelect(map(Option, array_sizes), label="Array Size", name="array_size", value="4.0kW",
                                        hx_trigger="change", hx_post=calculate, hx_target="#results"),
                        
                        LabelSelect(map(Option, tariffs), label="Tariffs", name="tariff", value="Price Cap 2024",
                                        hx_trigger="change", hx_post=calculate, hx_target="#results"),
                        cols=2
                    ),
                    LabelRange(label="Export Rate (£/kWh) (Rates aren't guaranteed long term - don't choose your install on optimistic values)",
                               value="0", step=0.01, min=0, max=0.15, name="export_rate"),
                    DivCentered(Button("Calculate", type="submit", cls=ButtonT.ghost)),
                ),
            ),
            Div(id="results"),
            cls="space-y-4",
        )
        )

# Explanatory text variables
annual_overview_text = ("This comparison shows how much you could save annually by installing solar. " \
                        "It currently assumes that future energy costs will remain constant for your selected tariff.")

monthly_breakdown_text = ("Monthly costs vary significantly throughout the year due to seasonal changes in both " \
                          "solar generation and energy consumption. Summer months typically show the highest savings " \
                          "due to increased solar output, while winter months may have minimal solar contribution.")

solar_vs_consumption_text = ("This chart compares your monthly solar generation against your energy consumption. " \
                            "When solar generation exceeds consumption, you'll export excess energy to the grid. " \
                            "The gap between these lines shows your remaining grid dependency.")

export_savings_text = ("Export revenue is earned when your solar system generates more electricity than you consume. " \
                       "Total monthly savings combine both the electricity you don't need to buy from the grid " \
                       "and the revenue from exporting excess energy. Note that export rates are typically lower than import rates.")

cumulative_projection_text = ("This projection shows how your savings accumulate over time compared to the initial " \
                             "system cost. The payback period is when cumulative savings equal your initial investment. " \
                             "This assumes constant energy prices and system performance - actual results may vary.")

intro_text = ("Use this calculator to estimate the financial benefits of installing a solar panel system. " \
              "Enter your preferred system size, select your current energy tariff, and set an export rate " \
              "to see detailed projections of costs, savings, and payback periods.")

configuration_help_text = ("• Array Size: Larger systems generate more electricity but cost more upfront\n" \
                          "• Tariff: Choose your current energy tariff for accurate cost calculations\n" \
                          "• Export Rate: The rate you'll be paid for excess energy sent to the grid")
serve()