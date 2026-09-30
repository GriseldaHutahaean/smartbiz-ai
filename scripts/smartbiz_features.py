"""Rule-based financial, pricing, inventory, and restock baselines."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

from ucs_production import ProductionOption, build_graph, uniform_cost_search


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "smartbiz_json"
REQUIRED_TABLES = (
    "products",
    "sales",
    "expenses",
    "inventory_history",
    "production_options",
)


def load_dataset(data_dir: Path = DEFAULT_DATA_DIR) -> dict[str, list[dict[str, object]]]:
    """Load the JSON tables used by the rule-based SmartBiz features."""
    tables: dict[str, list[dict[str, object]]] = {}
    for table_name in REQUIRED_TABLES:
        with (data_dir / f"{table_name}.json").open(encoding="utf-8") as data_file:
            records = json.load(data_file)
        if not isinstance(records, list):
            raise ValueError(f"{table_name}.json must contain a JSON array")
        tables[table_name] = records
    return tables


def analyze_finances(dataset: dict[str, list[dict[str, object]]]) -> dict[str, int | float]:
    """Summarize revenue, gross profit, expenses, and net profit."""
    product_costs = {
        str(product["product_id"]): int(product["hpp"]) + int(product["production_cost"])
        for product in dataset["products"]
    }
    revenue = sum(
        int(sale["quantity_sold"]) * int(sale["selling_price"])
        for sale in dataset["sales"]
    )
    cost_of_goods = sum(
        int(sale["quantity_sold"]) * product_costs[str(sale["product_id"])]
        for sale in dataset["sales"]
    )
    expenses = sum(int(expense["amount"]) for expense in dataset["expenses"])
    gross_profit = revenue - cost_of_goods
    net_profit = gross_profit - expenses
    return {
        "revenue": revenue,
        "cost_of_goods": cost_of_goods,
        "gross_profit": gross_profit,
        "expenses": expenses,
        "net_profit": net_profit,
        "net_margin": net_profit / revenue if revenue else 0.0,
    }


def recommend_prices(
    dataset: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    """Recommend prices that achieve each product's target margin on unit cost."""
    recommendations = []
    for product in dataset["products"]:
        unit_cost = int(product["hpp"]) + int(product["production_cost"])
        target_margin = float(product["target_margin"])
        if not 0 <= target_margin < 1:
            raise ValueError(f"Invalid target margin for {product['product_id']}")
        recommended_price = math.ceil(unit_cost / (1 - target_margin))
        current_price = int(product["selling_price"])
        recommendations.append(
            {
                "product_id": str(product["product_id"]),
                "product_name": str(product["product_name"]),
                "unit_cost": unit_cost,
                "current_price": current_price,
                "recommended_price": recommended_price,
                "target_margin": target_margin,
                "current_margin": (current_price - unit_cost) / current_price
                if current_price
                else 0.0,
            }
        )
    return recommendations


def get_inventory_status(
    dataset: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    """Calculate current product stock from the inventory movement ledger."""
    stock_by_product: dict[str, int] = defaultdict(int)
    for record in dataset["inventory_history"]:
        stock_by_product[str(record["product_id"])] += int(record["quantity_change"])

    return [
        {
            "product_id": str(product["product_id"]),
            "product_name": str(product["product_name"]),
            "current_stock": stock_by_product[str(product["product_id"])],
            "stock_threshold": int(product["stock_threshold"]),
            "target_stock": int(product["initial_stock"]),
        }
        for product in dataset["products"]
    ]


def forecast_stock(
    dataset: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    """Estimate stock runway from average sales per calendar day in the dataset."""
    sales = dataset["sales"]
    if sales:
        dates = [date.fromisoformat(str(sale["date"])) for sale in sales]
        observed_days = (max(dates) - min(dates)).days + 1
    else:
        observed_days = 0

    units_sold: dict[str, int] = defaultdict(int)
    for sale in sales:
        units_sold[str(sale["product_id"])] += int(sale["quantity_sold"])

    forecasts = []
    for stock in get_inventory_status(dataset):
        product_id = str(stock["product_id"])
        average_daily_sales = units_sold[product_id] / observed_days if observed_days else 0.0
        days_until_stockout = (
            stock["current_stock"] / average_daily_sales if average_daily_sales else None
        )
        forecasts.append(
            {
                "product_id": product_id,
                "product_name": stock["product_name"],
                "average_daily_sales": average_daily_sales,
                "current_stock": stock["current_stock"],
                "days_until_stockout": days_until_stockout,
                "observed_days": observed_days,
            }
        )
    return forecasts


def get_low_stock_alerts(
    dataset: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    """Return products at or below their configured stock threshold."""
    return [
        stock
        for stock in get_inventory_status(dataset)
        if stock["current_stock"] <= stock["stock_threshold"]
    ]


def recommend_restock(
    dataset: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    """Use UCS production options to find a least-cost plan up to target stock."""
    options_by_product: dict[str, list[ProductionOption]] = defaultdict(list)
    for record in dataset["production_options"]:
        options_by_product[str(record["product_id"])].append(
            ProductionOption(
                units=int(record["units_produced"]),
                cost=int(record["production_cost"]),
            )
        )

    recommendations = []
    for stock in get_inventory_status(dataset):
        current_stock = int(stock["current_stock"])
        target_stock = int(stock["target_stock"])
        if current_stock >= target_stock:
            continue

        options = options_by_product[str(stock["product_id"])]
        graph = build_graph(current_stock, target_stock, options)
        result = uniform_cost_search(graph, current_stock, target_stock)
        if result is None:
            production_units = None
            batch_count = None
            total_cost = None
        else:
            path, total_cost = result
            production_units = sum(decision.produced_units for decision in path)
            batch_count = len(path)

        recommendations.append(
            {
                "product_id": stock["product_id"],
                "product_name": stock["product_name"],
                "current_stock": current_stock,
                "target_stock": target_stock,
                "production_units": production_units,
                "batch_count": batch_count,
                "total_cost": total_cost,
            }
        )
    return recommendations