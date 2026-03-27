import heapq
import math
from cambc import Position, Environment, Direction

CARDINAL_DELTAS = [(0, 1), (0, -1), (1, 0), (-1, 0)]
DIAGONAL_DELTAS = [(1, 1), (-1, -1), (1, -1), (-1, 1)]
ALL_DELTAS = CARDINAL_DELTAS + DIAGONAL_DELTAS

class FloodFillCalculator:
    def __init__(self, map: list[Environment | None], w: int):
        self.map = map
        self.w = w
        self.h = len(map) // w

        self.area = self.w * self.h

        # query state
        self.target: Position | None = None
        self.origin: Position | None = None
        self.target_distance_squared: int = 0
        self.allow_diagonal: bool = False
        self.bypass_wall: bool = False
        self.deltas: list[tuple[int, int]] = CARDINAL_DELTAS
        self.walls: set = set()

    def is_in_bound(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def in_target_zone(self, x: int, y: int) -> bool:
        dx, dy = x - self.target.x, y - self.target.y
        return dx * dx + dy * dy < self.target_distance_squared

    def heuristic(self, x: int, y: int) -> float:
        dx, dy = abs(x - self.origin.x), abs(y - self.origin.y)
        return max(dx, dy) if self.allow_diagonal else dx + dy

    def is_walkable(self, x: int, y: int) -> bool:
        if not self.is_in_bound(x, y):
            return False
        cell = self.map[self.idx(x, y)]
        if cell in self.walls:
            return self.bypass_wall and self.in_target_zone(x, y)
        return True

    def jump_cardinal(self, x: int, y: int, dx: int, dy: int) -> tuple[int, int] | None:
        while True:
            # advance one step in the direction
            coord = x, y = x + dx, y + dy

            # wall or OOB -- not jump pt
            if not self.is_walkable(x, y): return None
            # goal -- is jump pt
            if self.in_target_zone(x, y) or coord == (self.origin.x, self.origin.y):
                return coord

            if dx == 0:
                # vertically forced neighbor
                # - cell above/below us blocked
                # - cell diagonally ahead open
                if (not self.is_walkable(x + 1, y) and self.is_walkable(x + 1, y + dy)) or \
                   (not self.is_walkable(x - 1, y) and self.is_walkable(x - 1, y + dy)):
                    return coord
            else:
                # horizontally forced neighbor
                # - cell beside us blocked
                # - cell diagonally ahead open
                if (not self.is_walkable(x, y + 1) and self.is_walkable(x + dx, y + 1)) or \
                   (not self.is_walkable(x, y - 1) and self.is_walkable(x + dx, y - 1)):
                    return coord

    def jump_diagonal(self, x: int, y: int, dx: int, dy: int) -> tuple[int, int] | None:
        while True:
            coord = x, y = x + dx, y + dy
            if not self.is_walkable(x, y): return None
            if self.in_target_zone(x, y) or coord == (self.origin.x, self.origin.y):
                return coord

            # if jump point found cardinally, then current cell is also a jump point
            if (self.jump_cardinal(x, y, dx, 0) is not None) or \
               (self.jump_cardinal(x, y, 0, dy) is not None):
                return coord

            # diagonal forced neighbor
            # - blocked in the axis we just moved along
            # - open diagonally ahead of it
            if (not self.is_walkable(x - dx, y) and self.is_walkable(x - dx, y + dy)) or \
               (not self.is_walkable(x, y - dy) and self.is_walkable(x + dx, y - dy)):
                return coord

    def identify_successors(self, cx: int, cy: int, g_current: float) -> list[tuple[float, int, int, int]]:
        successors = []

        for dx, dy in self.deltas:
            is_diagonal = dx != 0 and dy != 0
            jp = self.jump_diagonal(cx, cy, dx, dy) if is_diagonal else self.jump_cardinal(cx, cy, dx, dy)

            if jp is None: continue

            jx, jy = jp
            ji = self.idx(jx, jy)
            diagonal_penalty = 0.001 if is_diagonal else 0 # discourage diagonal if cardinal path exists -- can remove
            dist = max(abs(jx - cx), abs(jy - cy)) if self.allow_diagonal else (abs(jx - cx) + abs(jy - cy))
            new_g = 0 if self.in_target_zone(jx, jy) else g_current + dist + diagonal_penalty

            successors.append((new_g, ji, jx, jy))

        return successors

    def run(
        self,
        target: Position,
        origin: Position,
        ignore_ores: bool,
        target_distance_squared: int = 0,
        allow_diagonal: bool = False,
        bypass_wall: bool = False,
    ) -> list[float | None]:
        self.target = target
        self.origin = origin
        self.target_distance_squared = target_distance_squared
        self.bypass_wall = bypass_wall
        self.allow_diagonal = allow_diagonal
        self.deltas = ALL_DELTAS if allow_diagonal else CARDINAL_DELTAS
        self.walls = (
            {Environment.WALL} if ignore_ores
            else {Environment.WALL, Environment.ORE_AXIONITE, Environment.ORE_TITANIUM}
        )

        distance_map = [None] * self.area

        if not self.is_in_bound(target.x, target.y): return distance_map

        g_score = [math.inf] * self.area
        visited = set()

        ti = self.idx(target.x, target.y)
        g_score[ti] = 0
        distance_map[ti] = 0

        open_set = [(self.heuristic(target.x, target.y), target.x, target.y)]

        while open_set:
            _, cx, cy = heapq.heappop(open_set)
            ci = self.idx(cx, cy)

            if ci in visited: continue
            visited.add(ci)

            if cx == origin.x and cy == origin.y:
                return distance_map

            for new_g, ji, jx, jy in self.identify_successors(cx, cy, g_score[ci]):
                if ji in visited: continue
                if new_g < g_score[ji]:
                    g_score[ji] = new_g
                    distance_map[ji] = new_g
                    heapq.heappush(open_set, (new_g + self.heuristic(jx, jy), jx, jy))

        return distance_map
