import heapq
import math
from cambc import Position, Environment, Direction

CARDINAL_DELTAS = [(0, 1), (0, -1), (1, 0), (-1, 0)]
DIAGONAL_DELTAS = [(1, 1), (-1, -1), (1, -1), (-1, 1)]
ALL_DELTAS = CARDINAL_DELTAS + DIAGONAL_DELTAS
BRIDGE_DELTAS = [(dx, dy) for dx in range(-3, 4) for dy in range(-3, 4) if 0 < dx*dx + dy*dy <= 9]
BRIDGE_PENALTY = 5

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
        return dx * dx + dy * dy <= self.target_distance_squared

    def heuristic(self, x: int, y: int) -> float:
        dx, dy = abs(x - self.target.x), abs(y - self.target.y)
        return max(dx, dy) if self.allow_diagonal else dx + dy
    
    def is_walkable(self, x: int, y: int) -> bool:
        if not self.is_in_bound(x, y):
            return False
        cell = self.map[self.idx(x, y)]
        if cell is None:
            return True
        if cell in self.walls:
            if self.in_target_zone(x, y):
                return self.bypass_wall  # only passable if bypass_wall is set
            return False
        return True

    def jump_cardinal(self, x: int, y: int, dx: int, dy: int) -> tuple[int, int] | None:
        while True:
            # advance one step in the direction
            coord = x, y = x + dx, y + dy

            # wall or OOB -- not jump pt
            if not self.is_walkable(x, y): return None
            # goal -- is jump pt
            if self.in_target_zone(x, y):
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
            if self.in_target_zone(x, y):
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
    
    def natural_neighbors(self, dx: int, dy: int) -> list[tuple[int, int]]:
        """Returns the natural neighbors given incoming direction (dx, dy)."""
        if dx != 0 and dy != 0:
            # diagonal move: natural = forward-x, forward-y, forward-diagonal
            return [(dx, 0), (0, dy), (dx, dy)]
        elif dx != 0:
            # horizontal move: natural = forward only
            return [(dx, 0)]
        else:
            # vertical move: natural = forward only
            return [(0, dy)]

    def forced_neighbors(self, cx: int, cy: int, dx: int, dy: int) -> list[tuple[int, int]]:
        """Returns forced neighbors at (cx, cy) given incoming direction."""
        forced = []
        if dx != 0 and dy != 0:
            # diagonal: forced if blocked on one axis but open diagonally past it
            if not self.is_walkable(cx - dx, cy) and self.is_walkable(cx - dx, cy + dy):
                forced.append((-dx, dy))
            if not self.is_walkable(cx, cy - dy) and self.is_walkable(cx + dx, cy - dy):
                forced.append((dx, -dy))
        elif dx != 0:
            # horizontal: forced if blocked above/below, open diagonally ahead
            if not self.is_walkable(cx, cy + 1) and self.is_walkable(cx + dx, cy + 1):
                forced.append((dx, 1))
            if not self.is_walkable(cx, cy - 1) and self.is_walkable(cx + dx, cy - 1):
                forced.append((dx, -1))
        else:
            # vertical: forced if blocked left/right, open diagonally ahead
            if not self.is_walkable(cx + 1, cy) and self.is_walkable(cx + 1, cy + dy):
                forced.append((1, dy))
            if not self.is_walkable(cx - 1, cy) and self.is_walkable(cx - 1, cy + dy):
                forced.append((-1, dy))
        return forced

    def identify_successors(self, cx: int, cy: int, parent: tuple[int, int] | None, g_current: float) -> list[tuple[float, int, int, int]]:
        successors = []

        if parent is None:
            # start node: expand all directions
            dirs = self.deltas
        else:
            px, py = parent
            dx = cx - px
            dy = cy - py
            # normalise to unit direction
            dx = (dx > 0) - (dx < 0)
            dy = (dy > 0) - (dy < 0)
            dirs = self.natural_neighbors(dx, dy) + self.forced_neighbors(cx, cy, dx, dy)

        for dx, dy in dirs:
            is_diagonal = dx != 0 and dy != 0
            jp = self.jump_diagonal(cx, cy, dx, dy) if is_diagonal else self.jump_cardinal(cx, cy, dx, dy)

            if jp is None:
                continue

            jx, jy = jp
            ji = self.idx(jx, jy)
            diagonal_penalty = 0.001 if is_diagonal else 0
            dist = max(abs(jx - cx), abs(jy - cy)) if self.allow_diagonal else (abs(jx - cx) + abs(jy - cy))
            new_g = g_current + dist + diagonal_penalty

            successors.append((new_g, ji, jx, jy))

        return successors
    
    def _any_target_walkable(self) -> bool:
        tx, ty = self.target.x, self.target.y
        r = math.isqrt(self.target_distance_squared)
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx * dx + dy * dy <= self.target_distance_squared:
                    if self.is_walkable(tx + dx, ty + dy):
                        return True
        return False

    def run(
        self,
        target: Position,
        origin: Position,
        ignore_ores: bool,
        target_distance_squared: int = 0,
        allow_diagonal: bool = False,
        bypass_wall: bool = False,
    ) -> list[tuple[int, int]]:
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

        if not self.is_in_bound(target.x, target.y):
            return []
        if not self._any_target_walkable():
            return []
        if not allow_diagonal:
            return self._run_astar()
        g_score = [math.inf] * self.area
        visited = set()
        came_from = {}

        oi = self.idx(origin.x, origin.y)
        g_score[oi] = 0 
        open_set = [(self.heuristic(origin.x, origin.y), origin.x, origin.y)]
        while open_set:
            _, cx, cy = heapq.heappop(open_set)
            ci = self.idx(cx, cy)

            if ci in visited:
                continue
            visited.add(ci)

            if self.in_target_zone(cx, cy):
                path = []
                current = (cx, cy)
                while current != (self.origin.x, self.origin.y):
                    path.append(Position(current[0], current[1]))
                    ci = self.idx(*current)
                    if ci not in came_from:
                        break
                    current = came_from[ci]
                path.append(Position(self.origin.x, self.origin.y))
                path.reverse()
                return path

            # came_from stores (px, py) as before, but now pass parent to identify_successors
            for new_g, ji, jx, jy in self.identify_successors(cx, cy, came_from.get(ci), g_score[ci]):
                if ji in visited:
                    continue
                if new_g < g_score[ji]:
                    g_score[ji] = new_g
                    came_from[ji] = (cx, cy)
                    heapq.heappush(open_set, (new_g + self.heuristic(jx, jy), jx, jy))

        return []


    def _run_astar(self) -> list[Position]:
        g_score = [math.inf] * self.area
        visited = set()
        came_from = {}

        oi = self.idx(self.origin.x, self.origin.y)
        g_score[oi] = 0
        open_set = [(self.heuristic(self.origin.x, self.origin.y), self.origin.x, self.origin.y)]

        while open_set:
            _, cx, cy = heapq.heappop(open_set)
            ci = self.idx(cx, cy)

            if ci in visited:
                continue
            visited.add(ci)

            if self.in_target_zone(cx, cy):
                path = []
                current = (cx, cy)
                while current != (self.origin.x, self.origin.y):
                    path.append(Position(current[0], current[1]))
                    ci = self.idx(*current)
                    if ci not in came_from:
                        break
                    current = came_from[ci]
                path.append(Position(self.origin.x, self.origin.y))
                path.reverse()
                return path

            for dx, dy in BRIDGE_DELTAS:
                nx, ny = cx + dx, cy + dy
                if not self.is_walkable(nx, ny):
                    continue
                ni = self.idx(nx, ny)
                if ni in visited:
                    continue
                is_bridge = (dx, dy) not in CARDINAL_DELTAS
                cost = BRIDGE_PENALTY if is_bridge else 1
                new_g = g_score[ci] + cost
                if new_g < g_score[ni]:
                    g_score[ni] = new_g
                    came_from[ni] = (cx, cy)
                    heapq.heappush(open_set, (new_g + self.heuristic(nx, ny), nx, ny))

        return []