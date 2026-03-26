import heapq
import math
from cambc import Position, Environment, Direction

CARDINAL_DELTAS = [(0, 1), (0, -1), (1, 0), (-1, 0)]
DIAGONAL_DELTAS = [(1, 1), (-1, -1), (1, -1), (-1, 1)]
ALL_DELTAS = CARDINAL_DELTAS + DIAGONAL_DELTAS

def flood_fill(
    map: list[Environment | None],
    w: int,
    target: Position,
    origin: Position,
    ignore_ores: bool,
    target_distance_squared: int = 0,
    allow_diagonal: bool = False,
    bypass_wall: bool = False,
) -> list[float | None]:
    h = len(map) // w

    if not is_in_bound(target.x, target.y, w, h):
        return [None] * (w * h)

    WALLS = {Environment.WALL} if ignore_ores else {Environment.WALL, Environment.ORE_AXIONITE, Environment.ORE_TITANIUM}
    DELTAS = ALL_DELTAS if allow_diagonal else CARDINAL_DELTAS

    def idx(x, y) -> int:
        return y * w + x

    def in_target_zone(x, y) -> bool:
        dx, dy = x - target.x, y - target.y
        return dx * dx + dy * dy < target_distance_squared

    def heuristic(x, y) -> float:
        dx, dy = abs(x - origin.x), abs(y - origin.y)
        return max(dx, dy) if allow_diagonal else dx + dy

    distance_map = [None] * (w * h)  # None = unvisited/unreachable
    g_score = [math.inf] * (w * h)
    visited = set()

    ti = idx(target.x, target.y)
    g_score[ti] = 0
    distance_map[ti] = 0

    open_set = [(heuristic(target.x, target.y), target.x, target.y)]

    while open_set:
        _, cx, cy = heapq.heappop(open_set)

        ci = idx(cx, cy)
        if ci in visited:
            continue
        visited.add(ci)

        if cx == origin.x and cy == origin.y:
            return distance_map

        for dx, dy in DELTAS:
            nx, ny = cx + dx, cy + dy

            if not is_in_bound(nx, ny, w, h):
                continue

            ni = idx(nx, ny)
            if ni in visited:
                continue

            in_zone = in_target_zone(nx, ny)

            if map[ni] in WALLS and not (bypass_wall and in_zone):
                distance_map[ni] = math.inf
                visited.add(ni)
                continue

            is_diagonal = dx != 0 and dy != 0
            diagonal_penalty = 0.001 if is_diagonal else 0
            new_g = 0 if in_zone else g_score[ci] + 1 + diagonal_penalty

            if new_g < g_score[ni]:
                g_score[ni] = new_g
                distance_map[ni] = new_g
                heapq.heappush(open_set, (new_g + heuristic(nx, ny), nx, ny))

    return distance_map


def is_in_bound(x: int, y: int, w: int, h: int) -> bool:
    return 0 <= x < w and 0 <= y < h