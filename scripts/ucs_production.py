"""Baseline Uniform Cost Search untuk keputusan produksi SmartBiz AI.

Modul ini hanya menangani pencarian keputusan produksi pada persediaan.
Perhitungan HPP, laba, dan margin merupakan proses bisnis terpisah dari UCS.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from itertools import count


@dataclass(frozen=True)
class ProductionOption:
    """Satu pilihan batch produksi dan biaya produksinya."""

    units: int
    cost: int


@dataclass(frozen=True)
class Decision:
    """Edge pada graph: memproduksi sejumlah unit dengan biaya tertentu."""

    from_stock: int
    to_stock: int
    produced_units: int
    cost: int


def build_graph(
    start_stock: int,
    demand: int,
    production_options: list[ProductionOption],
) -> dict[int, list[Decision]]:
    """Membangun graph state stok sampai kebutuhan dapat dipenuhi.

    Node/state adalah jumlah stok pada suatu kondisi. Edge/action adalah
    keputusan memproduksi satu batch. State yang mencapai atau melewati demand
    menjadi goal dan tidak perlu dikembangkan lagi oleh pencarian.
    """
    graph: dict[int, list[Decision]] = {}
    states_to_expand = [start_stock]
    expanded_states: set[int] = set()

    while states_to_expand:
        current_stock = states_to_expand.pop()
        if current_stock in expanded_states or current_stock >= demand:
            continue

        expanded_states.add(current_stock)
        decisions: list[Decision] = []

        for option in production_options:
            next_stock = current_stock + option.units
            decisions.append(
                Decision(
                    from_stock=current_stock,
                    to_stock=next_stock,
                    produced_units=option.units,
                    cost=option.cost,
                )
            )
            if next_stock not in expanded_states:
                states_to_expand.append(next_stock)

        graph[current_stock] = decisions

    return graph


def uniform_cost_search(
    graph: dict[int, list[Decision]],
    start: int,
    goal: int,
) -> tuple[list[Decision], int] | None:
    """Mencari jalur menuju goal dengan total biaya produksi paling rendah.

    UCS selalu mengambil state dengan g(n) terkecil dari priority queue.
    Karena f(n) = g(n), tidak ada heuristik yang digunakan pada baseline ini.
    """
    queue_counter = count()
    frontier: list[tuple[int, int, int, list[Decision]]] = [
        (0, next(queue_counter), start, [])
    ]
    best_cost: dict[int, int] = {start: 0}

    while frontier:
        total_cost, _, current_stock, path = heapq.heappop(frontier)

        # Abaikan entri lama yang bukan lagi biaya terbaik untuk state ini.
        if total_cost != best_cost.get(current_stock):
            continue

        if current_stock >= goal:
            return path, total_cost

        for decision in graph.get(current_stock, []):
            next_cost = total_cost + decision.cost
            if next_cost < best_cost.get(decision.to_stock, float("inf")):
                best_cost[decision.to_stock] = next_cost
                heapq.heappush(
                    frontier,
                    (
                        next_cost,
                        next(queue_counter),
                        decision.to_stock,
                        [*path, decision],
                    ),
                )

    return None


def print_result(
    product_name: str,
    start_stock: int,
    demand: int,
    result: tuple[list[Decision], int] | None,
) -> None:
    """Menampilkan jalur keputusan dan penjelasan hasil UCS."""
    def rupiah(value: int) -> str:
        """Memformat biaya dengan pemisah ribuan yang umum di Indonesia."""
        return f"Rp{value:,}".replace(",", ".")

    print(f"Produk: {product_name}")
    print(f"Stok awal: {start_stock} unit")
    print(f"Kebutuhan/permintaan: {demand} unit")
    print()

    if result is None:
        print("Tidak ditemukan jalur produksi yang dapat memenuhi kebutuhan.")
        return

    path, total_cost = result
    print("Jalur keputusan produksi (hasil UCS):")
    print(f"  State awal: stok {start_stock} unit")
    current_stock = start_stock

    for step, decision in enumerate(path, start=1):
        print(
            f"  {step}. Produksi {decision.produced_units} unit "
            f"(biaya {rupiah(decision.cost)}) -> stok {decision.to_stock} unit"
        )
        current_stock = decision.to_stock

    print()
    print(f"State goal: stok {current_stock} unit memenuhi permintaan")
    print(f"Total biaya produksi minimum: {rupiah(total_cost)}")
    print(
        "Penjelasan: UCS membandingkan total biaya dari state awal dan selalu "
        "mengembangkan jalur dengan biaya kumulatif paling rendah. Jadi, "
        "jalur di atas adalah rekomendasi keputusan produksi termurah yang "
        "mencapai kebutuhan produk."
    )


def main() -> None:
    """Menjalankan contoh baseline persediaan dan produksi SmartBiz AI."""
    product_name = "Brownies"
    start_stock = 5
    demand = 20

    # Pilihan batch dan biaya di sini adalah biaya produksi nyata contoh.
    production_options = [
        ProductionOption(units=5, cost=25_000),
        ProductionOption(units=10, cost=50_000),
        ProductionOption(units=15, cost=75_000),
    ]

    graph = build_graph(start_stock, demand, production_options)
    result = uniform_cost_search(graph, start_stock, demand)
    print_result(product_name, start_stock, demand, result)


if __name__ == "__main__":
    main()