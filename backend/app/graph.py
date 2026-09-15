import math
from dataclasses import dataclass
from itertools import permutations
from .models import OrderBook


@dataclass
class Edge:
    source: str
    target: str
    rate: float
    book: OrderBook
    side: str

    @property
    def weight(self):
        return -math.log(self.rate)


def graph_edges(books):
    edges = []
    for b in books:
        edges.append(
            Edge(b.base, b.quote, b.bids[0].price * (1 - b.fee_rate), b, "sell")
        )
        edges.append(
            Edge(b.quote, b.base, (1 - b.fee_rate) / b.asks[0].price, b, "buy")
        )
    return edges


def has_negative_cycle(edges):
    nodes = {e.source for e in edges} | {e.target for e in edges}
    distance = {node: 0.0 for node in nodes}
    for i in range(len(nodes)):
        changed = False
        for e in edges:
            if distance[e.target] > distance[e.source] + e.weight + 1e-12:
                distance[e.target] = distance[e.source] + e.weight
                changed = True
                if i == len(nodes) - 1:
                    return True
        if not changed:
            return False
    return False


def triangular_cycles(books, start="USDT"):
    edges = graph_edges(books)
    if not has_negative_cycle(edges):
        return
    outgoing = {}
    for edge in edges:
        outgoing.setdefault(edge.source, []).append(edge)
    # Exact bounded negative-cycle enumeration: only three-leg cycles.
    for a in outgoing.get(start, []):
        for b in outgoing.get(a.target, []):
            if b.target == start:
                continue
            for c in outgoing.get(b.target, []):
                if c.target == start and a.weight + b.weight + c.weight < -1e-12:
                    yield [a, b, c]
