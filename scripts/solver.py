"""Genetic Algorithm production recommendations for the SmartBiz dataset."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from ucs_production import Decision, ProductionOption, build_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "smartbiz_json"


def _read_table(data_dir: Path, table_name: str) -> list[dict[str, object]]:
    with (data_dir / f"{table_name}.json").open(encoding="utf-8") as data_file:
        records = json.load(data_file)
    if not isinstance(records, list):
        raise ValueError(f"{table_name}.json must contain a JSON array")
    return records


def _states_that_reach_goal(
    graph: dict[int, list[Decision]],
    goal: int,
) -> set[int]:
    states = {
        state
        for state, decisions in graph.items()
        if any(decision.to_stock >= goal for decision in decisions)
    }
    changed = True
    while changed:
        changed = False
        for state, decisions in graph.items():
            if state not in states and any(decision.to_stock in states for decision in decisions):
                states.add(state)
                changed = True
    return states


def _random_feasible_chromosome(
    start: int,
    goal: int,
    options: list[ProductionOption],
    states_that_reach_goal: set[int],
    max_steps: int,
    rng: random.Random,
) -> list[int]:
    chromosome: list[int] = []
    stock = start

    while stock < goal and len(chromosome) < max_steps:
        viable = [
            (index, option)
            for index, option in enumerate(options)
            if option.units > 0
            and (
                stock + option.units >= goal
                or stock + option.units in states_that_reach_goal
            )
        ]
        if not viable:
            raise RuntimeError("Reachable production state has no viable batch option")
        option_index, option = rng.choice(viable)
        chromosome.append(option_index)
        stock += option.units

    if stock < goal:
        raise RuntimeError("Could not construct a feasible production chromosome")
    return chromosome


def _evaluate_chromosome(
    chromosome: list[int],
    start: int,
    goal: int,
    options: list[ProductionOption],
    max_steps: int,
) -> tuple[tuple[int, int, int], tuple[list[Decision], int] | None]:
    stock = start
    path: list[Decision] = []
    total_cost = 0

    for option_index in chromosome[:max_steps]:
        if stock >= goal:
            break
        option = options[option_index]
        next_stock = stock + option.units
        path.append(
            Decision(
                from_stock=stock,
                to_stock=next_stock,
                produced_units=option.units,
                cost=option.cost,
            )
        )
        stock = next_stock
        total_cost += option.cost

    if stock >= goal:
        return (0, 0, total_cost), (path, total_cost)
    return (1, goal - stock, total_cost), None


def _crossover(
    first: list[int],
    second: list[int],
    max_steps: int,
    rng: random.Random,
) -> list[int]:
    first_cut = rng.randrange(len(first) + 1)
    second_cut = rng.randrange(len(second) + 1)
    return (first[:first_cut] + second[second_cut:])[:max_steps]


def _mutate(
    chromosome: list[int],
    option_count: int,
    max_steps: int,
    rng: random.Random,
) -> list[int]:
    mutated = chromosome.copy()
    operations = ["replace", "insert", "delete"]
    if not mutated:
        operations = ["insert"]

    operation = rng.choice(operations)
    if operation == "replace" and mutated:
        mutated[rng.randrange(len(mutated))] = rng.randrange(option_count)
    elif operation == "insert" and len(mutated) < max_steps:
        position = rng.randrange(len(mutated) + 1)
        mutated.insert(position, rng.randrange(option_count))
    elif operation == "delete" and mutated:
        del mutated[rng.randrange(len(mutated))]
    return mutated[:max_steps]


def genetic_search(
    start_stock: int,
    target_stock: int,
    production_options: list[ProductionOption],
    *,
    population_size: int = 60,
    generations: int = 150,
    tournament_size: int = 3,
    elite_count: int = 2,
    mutation_rate: float = 0.15,
    seed: int | None = None,
) -> tuple[list[Decision], int] | None:
    """Find a low-cost batch sequence with tournament selection and elitism.

    Feasible chromosomes always rank ahead of infeasible chromosomes. Among
    feasible plans, lower total production cost wins.
    """
    if start_stock >= target_stock:
        return [], 0
    if population_size < 2:
        raise ValueError("population_size must be at least 2")
    if generations < 0:
        raise ValueError("generations must be non-negative")
    if not 1 <= tournament_size <= population_size:
        raise ValueError("tournament_size must be between 1 and population_size")
    if not 1 <= elite_count < population_size:
        raise ValueError("elite_count must be between 1 and population_size - 1")
    if not 0.0 <= mutation_rate <= 1.0:
        raise ValueError("mutation_rate must be between 0 and 1")
    if any(option.units < 0 or option.cost < 0 for option in production_options):
        raise ValueError("Production units and costs must be non-negative")
    if not production_options:
        return None

    graph = build_graph(start_stock, target_stock, production_options)
    states_that_reach_goal = _states_that_reach_goal(graph, target_stock)
    if start_stock not in states_that_reach_goal:
        return None

    max_steps = len(graph)
    rng = random.Random(seed)
    population = [
        _random_feasible_chromosome(
            start_stock,
            target_stock,
            production_options,
            states_that_reach_goal,
            max_steps,
            rng,
        )
        for _ in range(population_size)
    ]

    def fitness(chromosome: list[int]) -> tuple[int, int, int]:
        return _evaluate_chromosome(
            chromosome,
            start_stock,
            target_stock,
            production_options,
            max_steps,
        )[0]

    for _ in range(generations):
        ranked_population = sorted(population, key=fitness)
        next_population = [chromosome.copy() for chromosome in ranked_population[:elite_count]]

        while len(next_population) < population_size:
            first = min(
                (population[index] for index in rng.sample(range(population_size), tournament_size)),
                key=fitness,
            )
            second = min(
                (population[index] for index in rng.sample(range(population_size), tournament_size)),
                key=fitness,
            )
            child = _crossover(first, second, max_steps, rng)
            if rng.random() < mutation_rate:
                child = _mutate(child, len(production_options), max_steps, rng)
            next_population.append(child)

        population = next_population

    best = min(population, key=fitness)
    _, result = _evaluate_chromosome(
        best,
        start_stock,
        target_stock,
        production_options,
        max_steps,
    )
    return result


def recommend_all(
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    product_id: str | None = None,
    population_size: int = 60,
    generations: int = 150,
    tournament_size: int = 3,
    elite_count: int = 2,
    mutation_rate: float = 0.15,
    seed: int | None = None,
) -> list[dict[str, object]]:
    """Recommend production plans using the existing SmartBiz JSON tables."""
    products = _read_table(data_dir, "products")
    if product_id is not None:
        products = [product for product in products if product["product_id"] == product_id]
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
    for product_index, product in enumerate(products):
        product_id = str(product["product_id"])
        current_stock = stock_by_product[product_id]
        target_stock = int(product["initial_stock"])
        product_seed = None if seed is None else seed + product_index
        result = genetic_search(
            current_stock,
            target_stock,
            options_by_product[product_id],
            population_size=population_size,
            generations=generations,
            tournament_size=tournament_size,
            elite_count=elite_count,
            mutation_rate=mutation_rate,
            seed=product_seed,
        )

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
    parser.add_argument("--seed", type=int, help="Seed agar hasil GA dapat direproduksi")
    parser.add_argument("--population-size", type=int, default=60)
    parser.add_argument("--generations", type=int, default=150)
    parser.add_argument("--tournament-size", type=int, default=3)
    parser.add_argument("--elite-count", type=int, default=2)
    parser.add_argument("--mutation-rate", type=float, default=0.15)
    args = parser.parse_args()

    recommendations = recommend_all(
        args.data_dir,
        product_id=args.product_id,
        population_size=args.population_size,
        generations=args.generations,
        tournament_size=args.tournament_size,
        elite_count=args.elite_count,
        mutation_rate=args.mutation_rate,
        seed=args.seed,
    )
    if args.product_id and not recommendations:
        parser.error(f"product_id tidak ditemukan: {args.product_id}")

    print("ID | Produk | Stok | Target | Produksi | Batch | Biaya GA")
    for item in recommendations:
        cost = item["total_cost"]
        cost_text = _rupiah(int(cost)) if cost is not None else "Tidak tersedia"
        print(
            f"{item['product_id']} | {item['product_name']} | "
            f"{item['current_stock']} | {item['target_stock']} | "
            f"{item['production_units']} | {item['batch_count']} | {cost_text}"
        )

    print(f"Produk dianalisis: {len(recommendations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())