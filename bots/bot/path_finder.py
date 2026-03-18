from cambc import Position, Environment, Controller, Direction
from collections import deque
import math

def flood_fill(map: list[list[Environment | None]], target: Position, origin: Position, distance_map = None):
    width = len(map)
    height = len(map[0])
    if not distance_map:
        distance_map = [[None] * height for _ in range(width)]

    distance_map[target.x][target.y] = 0
    q = deque([target])
    while len(q) > 0:
        p = q.popleft()
        cardinal_positions = get_cardinal(p, width, height)
        for c_p in cardinal_positions:
            if (not map[c_p.x][c_p.y] in [Environment.EMPTY, None]):
                distance_map[c_p.x][c_p.y] = math.inf
                continue
            if (c_p.x == origin.x and c_p.y == origin.y):
                return distance_map
            if (distance_map[c_p.x][c_p.y] == None):
                distance_map[c_p.x][c_p.y] = distance_map[p.x][p.y] + 1
                q.append(c_p)

    return distance_map

    
def get_cardinal(p: Position, w: int, h: int):
    def is_in_bound(pos: Position):
        return pos.x in range(w) and pos.y in range(h)
    cardinal_directions = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
    candidate_positions = [p.add(d) for d in cardinal_directions]
    return [d for d in candidate_positions if is_in_bound(d)]
