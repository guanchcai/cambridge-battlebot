from cambc import Position, Environment, Controller, Direction
from collections import deque
import random
import math
from array import array

def flood_fill(map: list[list[Environment | None]], target: Position, origin: Position, target_distance_squared = 0):
    width = len(map)
    height = len(map[0])
    distance_map = [[None] * height for _ in range(width)]
    visited = bytearray(width * height)  # all False by default
    dist = array('i', [0] * (width * height)) 

    distance_map[target.x][target.y] = 0
    q = deque([target])
    while len(q) > 0:
        p = q.popleft()
        cardinal_positions = get_cardinal(p, width, height)
        for c_p in cardinal_positions:
            if distance_map[c_p.x][c_p.y] is not None:  # already processed
                continue
            if c_p.distance_squared(target) <= target_distance_squared:
                distance_map[c_p.x][c_p.y] = 0
                q.append(c_p)
                continue
            if (map[c_p.x][c_p.y] in [Environment.WALL, Environment.ORE_AXIONITE, Environment.ORE_TITANIUM]):
                distance_map[c_p.x][c_p.y] = math.inf
                continue
            if (c_p.x == origin.x and c_p.y == origin.y):
                distance_map[c_p.x][c_p.y] = distance_map[p.x][p.y] + 1                
                return distance_map
            if (distance_map[c_p.x][c_p.y] == None):
                distance_map[c_p.x][c_p.y] = distance_map[p.x][p.y] + 1
                q.append(c_p)

    return distance_map

    
def get_cardinal(p: Position, w: int, h: int):
    def is_in_bound(pos: Position):
        return 0 <= pos.x < w and 0 <= pos.y < h
    cardinal_directions = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
    random.shuffle(cardinal_directions)
    candidate_positions = [p.add(d) for d in cardinal_directions]
    return [d for d in candidate_positions if is_in_bound(d)]
