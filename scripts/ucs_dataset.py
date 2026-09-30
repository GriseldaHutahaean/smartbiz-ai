"""Run UCS production recommendations against the bundled SmartBiz dataset."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from ucs_production import ProductionOption, build_graph, uniform_cost_search


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "smartbiz_json"


def _read_table(data_dir: Path, table_name: str) -> list[dict[str, object]]:
    with (data_dir / f"{table_name}.json").open(encoding="utf-8") as data_file:
        records = json.load(data_file)
    if not isinstance(records, list):
        raise ValueError(f"{table_name}.json must contain a JSON array")
    return records


def recommend_all(data_dir: Path = DEFAULT_DATA_DIR) -> list[dict[str, object]]:
    """Recommend the least-cost production plan to restore each product's target stock."""
    products = _read_table(data_dir, "products")
    option_records = _read_table(data_dir, "production_options")
    inventory_records = _read_table(data_dir, "inventory_history")

    options_by_product: dict[str, list[ProductionOption]] = defaultdict(list)
    for record in option_records:
        options_by_product[str(record["product_id"])].append(
            ProductionOption(
                units=int(record["units_produced"]),
                cost=int(record["production_cost"]),
            )
        )

    stock_by_product: dict[str, int] = defaultdict(int)
    for record in inventory_records:
        stock_by_product[str(record["product_id"])] += int(record["quantity_change"])

    recommendations: list[dict[str, object]] = []
    for product in products:
        product_id = str(product["product_id"])
        current_stock = stock_by_product[product_id]
        target_stock = int(product["initial_stock"])
        graph = build_graph(
            current_stock,
            target_stock,
            options_by_product[product_id],
        )
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
                "product_id": product_id,
                "product_name": str(product["product_name"]),
                "current_stock": current_stock,
                "target_stock": target_stock,
                "production_units": production_units,
                "batch_count": batch_count,
                "total_cost": total_cost,
            }
        )

    return recommendations


def _rupiah(value: int) -> str:
    return f"Rp{value:,}".replace(",", ".")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Folder berisi file JSON dataset (default: data/smartbiz_json)",
    )
    parser.add_argument("--product-id", help="Tampilkan rekomendasi satu produk, misalnya P001")
    args = parser.parse_args()

    recommendations = recommend_all(args.data_dir)
    if args.product_id:
        recommendations = [
            item for item in recommendations if item["product_id"] == args.product_id
        ]
        if not recommendations:
            parser.error(f"product_id tidak ditemukan: {args.product_id}")

    print("ID | Produk | Stok | Target | Produksi | Batch | Biaya minimum")
    for item in recommendations:
        cost = item["total_cost"]
        cost_text = _rupiah(int(cost)) if cost is not None else "Tidak tersedia"
        print(
            f"{item['product_id']} | {item['product_name']} | "
            f"{item['current_stock']} | {item['target_stock']} | "
            f"{item['production_units']} | {item['batch_count']} | {cost_text}"
        )

    needing_production = sum(
        item["production_units"] is not None and item["production_units"] > 0
        for item in recommendations
    )
    print(
        f"Produk dianalisis: {len(recommendations)}; "
        f"perlu produksi: {needing_production}; "
        f"total biaya minimum: {_rupiah(sum(int(item['total_cost'] or 0) for item in recommendations))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())