from path_finder_floodfill_jps import FloodFillCalculator
from cambc import Position, Environment
import math

maze = [
    [Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY],
    [Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY],
    [Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY],
    [Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY],
    [Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY],
    [Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY],
    [Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY],
    [Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY],
    [Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY],
    [Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL],
    [Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY],
    [Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY],
    [Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY],
    [Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY],
    [Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY],
    [Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL],
    [Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL],
    [Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY],
    [Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY],
    [Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.EMPTY, Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.WALL,  Environment.EMPTY, Environment.WALL,  Environment.EMPTY],
]

SYMBOLS = {
    Environment.EMPTY: "  ",
    Environment.WALL:  "██",
}

def print_maze():
    for row in maze:
        print("".join(SYMBOLS[cell] for cell in row))

def print_dist_map(d_map):
    def map_to_string(c):
        if (c == None):
            return "__"
        if (math.isinf(c)):
            return "██"
        return f"{c:02d}"
    for row in d_map:
        print("".join(map_to_string(cell) for cell in row))

print_maze()
calculator = FloodFillCalculator()
d_map = flood_fill(maze, Position(19, 19), Position(0, 0), 20, 20)
print_dist_map(d_map)
