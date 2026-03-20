import heapq
import math
from cambc import Position, Environment, Direction

CARDINAL_DELTAS = [(0, 1), (0, -1), (1, 0), (-1, 0)]

def flood_fill(map: list[list[Environment | None]], target: Position, origin: Position, target_distance_squared=0):
    width = len(map)
    height = len(map[0])
    distance_map = [[None] * height for _ in range(width)]
    g_score = [[math.inf] * height for _ in range(width)]

    tx, ty = target.x, target.y
    ox, oy = origin.x, origin.y
    print((ox, oy))

    if not is_in_bound(tx, ty, width, height):
        return distance_map

    def is_target_zone(x, y) -> bool:
        dx, dy = x - tx, y - ty
        return dx*dx + dy*dy < target_distance_squared

    def heuristic(x, y) -> int:
        return abs(x - ox) + abs(y - oy)
    
    g_score[tx][ty] = 0
    distance_map[tx][ty] = 0
    open_set = [(heuristic(tx, ty), tx, ty)]

    WALL_TYPES = (Environment.WALL, Environment.ORE_AXIONITE, Environment.ORE_TITANIUM)

    while open_set:
        _, cx, cy = heapq.heappop(open_set)

        if cx == ox and cy == oy:
            return distance_map

        for dx, dy in CARDINAL_DELTAS:
            nx, ny = cx + dx, cy + dy

            if not (0 <= nx < width and 0 <= ny < height):
                continue

            if distance_map[nx][ny] is not None:
                continue

            if map[nx][ny] in WALL_TYPES and not is_target_zone(nx, ny):
                distance_map[nx][ny] = math.inf
                continue

            new_g = 0 if is_target_zone(nx, ny) else g_score[cx][cy] + 1

            if new_g < g_score[nx][ny]:
                g_score[nx][ny] = new_g
                distance_map[nx][ny] = new_g
                heapq.heappush(open_set, (new_g + heuristic(nx, ny), nx, ny))
    print("I HATE YOU I HATE YOU I HATE YOU WHY WHY WHY WHY WHY WHY WHY")
    return distance_map


def get_cardinal(p: Position, w: int, h: int):
    return [
        Position(p.x + dx, p.y + dy)
        for dx, dy in CARDINAL_DELTAS
        if is_in_bound(p.x + dx, p.y + dy)
    ]

def is_in_bound(x: int, y: int, w: int, h: int):
    return 0 <= x < w and 0 <= y < h