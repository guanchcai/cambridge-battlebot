import heapq
import math
from cambc import Position, Environment
from utils.helper_functions import is_in_bound, direction_to_delta
from utils.constants import DeltaTypes
from utils.path_queue import PathQueue

class AStarPathfinder:

    def __init__(self, _map: list[Environment | None], w: int):
        self.map = _map
        self.w = w
        self.h = len(_map) // w
        self.area = self.w * self.h

    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def heuristic(self, x: int, y: int, tx: int, ty: int, allow_diag: bool):
        dx = abs(x - tx)
        dy = abs(y - ty)

        if allow_diag:
            return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)

        return dx + dy

    def is_walkable(self, x, y, walls, target, bypass_wall, target_distance_squared):
        if not is_in_bound(x, y, self.w, self.h):
            print(f"  ({x},{y}) out of bounds")
            return False

        cell = self.map[self.idx(x, y)]

        if cell is None:
            return True

        if cell in walls:
            dx = x - target.x
            dy = y - target.y
            if dx * dx + dy * dy <= target_distance_squared:
                return bypass_wall
            return False

        return True

    def reconstruct_path(self, came_from, current):
        path = []

        while current in came_from:
            path.append(Position(*current))
            current = came_from[current]

        path.append(Position(*current))
        path.reverse()

        return PathQueue(path)

    def run(
        self,
        origin: Position,
        target: Position,
        ignore_ores: bool,
        delta_type: DeltaTypes,
        target_distance_squared: int = 0,
        bypass_wall: bool = False,
    ):
        print("Called")
        allow_diag = delta_type == DeltaTypes.ALL
        deltas = direction_to_delta(delta_type)

        walls = (
            {Environment.WALL}
            if ignore_ores
            else {
                Environment.WALL,
                Environment.ORE_TITANIUM,
                Environment.ORE_AXIONITE,
            }
        )

        # Early exit if already within target distance
        if (
            (origin.x - target.x) ** 2 +
            (origin.y - target.y) ** 2
        ) <= target_distance_squared:
            return PathQueue([Position(origin.x, origin.y)])

        open_set = []
        heapq.heappush(open_set, (0, origin.x, origin.y))

        came_from = {}
        g_score = [math.inf] * self.area
        g_score[self.idx(origin.x, origin.y)] = 0

        closed_set = set()

        while open_set:
            _, cx, cy = heapq.heappop(open_set)

            # Skip already-settled nodes
            if (cx, cy) in closed_set:
                continue
            closed_set.add((cx, cy))

            if (
                (cx - target.x) ** 2 +
                (cy - target.y) ** 2
            ) <= target_distance_squared:
                cell = self.map[self.idx(cx, cy)]
                if bypass_wall or cell not in walls:
                    return self.reconstruct_path(came_from, (cx, cy))

            ci = self.idx(cx, cy)

            for dx, dy, penalty in (
                direction_to_delta(DeltaTypes.CARDINAL) 
                if (cx == origin.x and cy == origin.y and delta_type == DeltaTypes.BRIDGE) else deltas
            ):
                nx = cx + dx
                ny = cy + dy

                if (nx, ny) in closed_set:
                    continue

                # Always allow stepping onto the target cell regardless of
                # walkability — it may be a wall or ore the caller wants to
                # path toward
                is_target_cell = (
                    (nx - target.x) ** 2 +
                    (ny - target.y) ** 2
                ) <= target_distance_squared

                if not is_target_cell and not self.is_walkable(
                    nx, ny, walls, target, bypass_wall, target_distance_squared
                ):
                    continue
                
                if is_target_cell and not bypass_wall:
                    cell = self.map[self.idx(nx, ny)]
                    if cell is not None and cell in walls:
                        continue

                ni = self.idx(nx, ny)
                new_g = g_score[ci] + penalty

                if new_g >= g_score[ni]:
                    continue

                came_from[(nx, ny)] = (cx, cy)
                g_score[ni] = new_g
                f_score = new_g + self.heuristic(
                    nx, ny, target.x, target.y, allow_diag
                )
                heapq.heappush(open_set, (f_score, nx, ny))

        return None