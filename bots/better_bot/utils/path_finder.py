import heapq
import math
from cambc import Position, Environment
from utils.helper_functions import is_in_bound, direction_to_delta
from utils.constants import DeltaTypes
from utils.path_queue import PathQueue

_SENTINEL = -1  # marks unvisited in came_from

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

    def reconstruct_path(self, came_from, start_i, current_i):
        path = []
        ci = current_i
        w = self.w
        while ci != start_i:
            path.append(Position(ci % w, ci // w))
            ci = came_from[ci]
        path.append(Position(start_i % w, start_i // w))
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
        allow_diag = delta_type == DeltaTypes.ALL
        w, h = self.w, self.h
        _map = self.map
        area = self.area

        walls = (
            {Environment.WALL}
            if ignore_ores
            else {Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE}
        )

        ox, oy = origin.x, origin.y
        tx, ty = target.x, target.y
        start_i = oy * w + ox

        # Early exit if already within target distance
        if (ox - tx) ** 2 + (oy - ty) ** 2 <= target_distance_squared:
            return PathQueue([Position(ox, oy)])

        # --- Hoist deltas out of the loop ---
        deltas = direction_to_delta(delta_type)
        cardinal_deltas = direction_to_delta(DeltaTypes.CARDINAL)
        is_bridge = delta_type == DeltaTypes.BRIDGE

        open_set = []
        heapq.heappush(open_set, (0, ox, oy))

        # Use int array for came_from instead of dict — much faster
        came_from = [-1] * area
        came_from[start_i] = start_i  # sentinel: start points to itself

        g_score = [math.inf] * area
        g_score[start_i] = 0

        closed_set = bytearray(area)

        while open_set:
            f, cx, cy = heapq.heappop(open_set)
            ci = cy * w + cx

            if closed_set[ci]:
                continue
            closed_set[ci] = 1

            if (cx - tx) ** 2 + (cy - ty) ** 2 <= target_distance_squared:
                cell = _map[ci]
                if bypass_wall or cell not in walls:
                    return self.reconstruct_path(came_from, start_i, ci)

            # Pick delta set — only differs on first step for BRIDGE
            cur_deltas = cardinal_deltas if (is_bridge and cx == ox and cy == oy) else deltas

            g_ci = g_score[ci]

            for dx, dy, penalty in cur_deltas:
                nx = cx + dx
                ny = cy + dy

                if nx < 0 or nx >= w or ny < 0 or ny >= h:
                    continue

                ni = ny * w + nx
                if closed_set[ni]:
                    continue

                is_target_cell = (nx - tx) ** 2 + (ny - ty) ** 2 <= target_distance_squared

                if not is_target_cell:
                    # Inline walkability — skip function call overhead
                    cell = _map[ni]
                    if cell is not None and cell in walls:
                        dx2 = nx - tx
                        dy2 = ny - ty
                        if dx2 * dx2 + dy2 * dy2 > target_distance_squared or not bypass_wall:
                            continue
                else:
                    if not bypass_wall:
                        cell = _map[ni]
                        if cell is not None and cell in walls:
                            continue

                new_g = g_ci + penalty
                if new_g >= g_score[ni]:
                    continue

                came_from[ni] = ci
                g_score[ni] = new_g
                f_score = new_g + self.heuristic(nx, ny, tx, ty, allow_diag)
                heapq.heappush(open_set, (f_score, nx, ny))

        return None