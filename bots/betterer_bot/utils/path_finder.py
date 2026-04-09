import heapq
import math
from cambc import Position, Environment
from utils.tile_info import TileData
from utils.helper_functions import is_in_bound, direction_to_delta
from utils.constants import DeltaTypes
from utils.path_queue import PathQueue

_SENTINEL = -1


class AStarPathfinder:

    def __init__(self, _map: list[TileData | None], w: int):
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

    def reconstruct_path_bidir(self, came_from_fwd, came_from_bwd, start_i, meet_i):
        w = self.w

        fwd = []
        ci = meet_i
        while ci != start_i:
            fwd.append(Position(ci % w, ci // w))
            ci = came_from_fwd[ci]
        fwd.append(Position(start_i % w, start_i // w))
        fwd.reverse()

        ci = came_from_bwd[meet_i]
        while came_from_bwd[ci] != ci:
            fwd.append(Position(ci % w, ci // w))
            ci = came_from_bwd[ci]
        fwd.append(Position(ci % w, ci // w))

        return PathQueue(fwd)

    def is_passable(self, ni: int, walls, include_barriers=False):
        cell = self.map[ni]
        return cell is None or cell.passable(walls) or (not include_barriers and cell.destroyable())

    def run(
        self,
        origin: Position,
        target: Position,
        ignore_ores: bool,
        delta_type: DeltaTypes,
        target_distance_squared: int = 0,
        bypass_wall: bool = False,
        include_barriers=False,
    ):
        allow_diag = delta_type == DeltaTypes.ALL
        w           = self.w
        h           = self.h
        area        = self.area
        _map        = self.map

        walls = (
            {Environment.WALL}
            if ignore_ores
            else {Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE}
        )

        ox, oy = origin.x, origin.y
        tx, ty = target.x, target.y
        start_i = oy * w + ox

        if (ox - tx) ** 2 + (oy - ty) ** 2 <= target_distance_squared:
            return PathQueue([Position(ox, oy)])

        deltas          = direction_to_delta(delta_type)
        cardinal_deltas = direction_to_delta(DeltaTypes.CARDINAL)
        is_bridge       = delta_type == DeltaTypes.BRIDGE

        # ── sanity: origin has at least one passable neighbor ─────────────────
        has_fwd_neighbors = False
        for ddx, ddy, _ in deltas:
            nx, ny = ox + ddx, oy + ddy
            if 0 <= nx < w and 0 <= ny < h:
                if self.is_passable(ny * w + nx, walls, include_barriers):
                    has_fwd_neighbors = True
                    break
        if not has_fwd_neighbors:
            print(f"[ASTAR] FAILED (origin surrounded) origin=({ox},{oy}) target=({tx},{ty})")
            return None

        # ── sanity: target has at least one passable neighbor ─────────────────
        has_bwd_neighbors = False
        for ddx, ddy, _ in deltas:
            nx, ny = tx + ddx, ty + ddy
            if 0 <= nx < w and 0 <= ny < h:
                if self.is_passable(ny * w + nx, walls, include_barriers):
                    has_bwd_neighbors = True
                    break
        if not has_bwd_neighbors:
            print(f"[ASTAR] FAILED (target surrounded) origin=({ox},{oy}) target=({tx},{ty})")
            return None

        # ── forward init ──────────────────────────────────────────────────────
        open_fwd      = [(0.0, ox, oy)]
        came_from_fwd = [-1] * area
        g_fwd         = [math.inf] * area
        closed_fwd    = bytearray(area)

        came_from_fwd[start_i] = start_i
        g_fwd[start_i]         = 0.0

        # ── backward init ─────────────────────────────────────────────────────
        open_bwd      = []
        came_from_bwd = [-1] * area
        g_bwd         = [math.inf] * area
        closed_bwd    = bytearray(area)

        r = int(math.isqrt(target_distance_squared))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= target_distance_squared:
                    nx, ny = tx + dx, ty + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        ni   = ny * w + nx
                        cell = _map[ni]
                        is_open    = cell is None or cell.passable(walls)
                        is_barrier = cell is not None and cell.destroyable()
                        if bypass_wall or is_open or (include_barriers and is_barrier):
                            came_from_bwd[ni] = ni
                            g_bwd[ni]         = 0.0
                            heapq.heappush(open_bwd, (0.0, nx, ny))

        if not open_bwd:
            print(f"[ASTAR] FAILED (no valid landing zone) origin=({ox},{oy}) target=({tx},{ty})")
            return None

        # ── cache heuristic method and sqrt2 locally ──────────────────────────
        sqrt2_minus_1 = math.sqrt(2) - 1
        heappush      = heapq.heappush
        heappop       = heapq.heappop

        best      = math.inf
        meet_node = -1

        # ── main loop (fully inlined, no closure overhead) ────────────────────
        while open_fwd and open_bwd:
            f_fwd = open_fwd[0][0]
            f_bwd = open_bwd[0][0]

            if meet_node != -1 and (f_fwd if f_fwd < f_bwd else f_bwd) >= best:
                break

            # pick which side to expand
            if f_fwd <= f_bwd:
                # ── forward step ──────────────────────────────────────────────
                f, cx, cy = heappop(open_fwd)
                ci = cy * w + cx
                if closed_fwd[ci]:
                    continue
                closed_fwd[ci] = 1

                if closed_bwd[ci]:
                    candidate = g_fwd[ci] + g_bwd[ci]
                    if candidate < best:
                        best      = candidate
                        meet_node = ci

                cur_deltas = cardinal_deltas if is_bridge else deltas
                g_ci = g_fwd[ci]

                for ddx, ddy, penalty in cur_deltas:
                    nx = cx + ddx
                    ny = cy + ddy
                    if nx < 0 or nx >= w or ny < 0 or ny >= h:
                        continue
                    ni = ny * w + nx
                    if closed_fwd[ni]:
                        continue

                    cell = _map[ni]
                    passable = cell is None or cell.passable(walls) or (not include_barriers and cell.destroyable() if cell else False)
                    if not passable:
                        if is_bridge and (cx != ox or cy != oy):
                            # wall hit — try all bridge deltas from current position
                            for bddx, bddy, bpenalty in deltas:
                                bnx = cx + bddx
                                bny = cy + bddy
                                if bnx < 0 or bnx >= w or bny < 0 or bny >= h:
                                    continue
                                bni = bny * w + bnx
                                if closed_fwd[bni]:
                                    continue
                                bcell = _map[bni]
                                bpassable = bcell is None or bcell.passable(walls) or (not include_barriers and bcell.destroyable() if bcell else False)
                                if not bpassable:
                                    continue
                                bbarrier_cost = 5 if (bcell is not None and bcell.destroyable()) else 0
                                new_g = g_ci + bpenalty + bbarrier_cost
                                if new_g >= g_fwd[bni]:
                                    continue
                                came_from_fwd[bni] = ci
                                g_fwd[bni]         = new_g
                                if closed_bwd[bni]:
                                    candidate = new_g + g_bwd[bni]
                                    if candidate < best:
                                        best      = candidate
                                        meet_node = bni
                                dx_ = bnx - tx
                                dy_ = bny - ty
                                if allow_diag:
                                    adx, ady = (dx_ if dx_ >= 0 else -dx_), (dy_ if dy_ >= 0 else -dy_)
                                    h_val = (adx if adx > ady else ady) + sqrt2_minus_1 * (adx if adx < ady else ady)
                                else:
                                    h_val = (dx_ if dx_ >= 0 else -dx_) + (dy_ if dy_ >= 0 else -dy_)
                                heappush(open_fwd, (new_g + h_val, bnx, bny))
                        elif bypass_wall:
                            dx2 = nx - tx
                            dy2 = ny - ty
                            if dx2 * dx2 + dy2 * dy2 > target_distance_squared:
                                continue
                        else:
                            continue
                        continue  # wall cell itself is never added to path

                    barrier_cost = 5 if (cell is not None and cell.destroyable()) else 0
                    new_g = g_ci + penalty + barrier_cost
                    if new_g >= g_fwd[ni]:
                        continue

                    came_from_fwd[ni] = ci
                    g_fwd[ni]         = new_g

                    if closed_bwd[ni]:
                        candidate = new_g + g_bwd[ni]
                        if candidate < best:
                            best      = candidate
                            meet_node = ni

                    dx_ = nx - tx
                    dy_ = ny - ty
                    if allow_diag:
                        adx, ady = (dx_ if dx_ >= 0 else -dx_), (dy_ if dy_ >= 0 else -dy_)
                        h_val = (adx if adx > ady else ady) + sqrt2_minus_1 * (adx if adx < ady else ady)
                    else:
                        h_val = (dx_ if dx_ >= 0 else -dx_) + (dy_ if dy_ >= 0 else -dy_)
                    heappush(open_fwd, (new_g + h_val, nx, ny))

            else:
                # ── backward step ─────────────────────────────────────────────
                f, cx, cy = heappop(open_bwd)
                ci = cy * w + cx
                if closed_bwd[ci]:
                    continue
                closed_bwd[ci] = 1

                if closed_fwd[ci]:
                    candidate = g_bwd[ci] + g_fwd[ci]
                    if candidate < best:
                        best      = candidate
                        meet_node = ci

                cur_deltas = cardinal_deltas if is_bridge else deltas
                g_ci = g_bwd[ci]

                for ddx, ddy, penalty in cur_deltas:
                    nx = cx + ddx
                    ny = cy + ddy
                    if nx < 0 or nx >= w or ny < 0 or ny >= h:
                        continue
                    ni = ny * w + nx
                    if closed_bwd[ni]:
                        continue

                    cell = _map[ni]
                    passable = cell is None or cell.passable(walls) or (not include_barriers and cell.destroyable() if cell else False)
                    if not passable:
                        if is_bridge and (cx != tx or cy != ty):
                            # wall hit — try all bridge deltas from current position
                            for bddx, bddy, bpenalty in deltas:
                                bnx = cx + bddx
                                bny = cy + bddy
                                if bnx < 0 or bnx >= w or bny < 0 or bny >= h:
                                    continue
                                bni = bny * w + bnx
                                if closed_bwd[bni]:
                                    continue
                                bcell = _map[bni]
                                bpassable = bcell is None or bcell.passable(walls) or (not include_barriers and bcell.destroyable() if bcell else False)
                                if not bpassable:
                                    continue
                                bbarrier_cost = 5 if (bcell is not None and bcell.destroyable()) else 0
                                new_g = g_ci + bpenalty + bbarrier_cost
                                if new_g >= g_bwd[bni]:
                                    continue
                                came_from_bwd[bni] = ci
                                g_bwd[bni]         = new_g
                                if closed_fwd[bni]:
                                    candidate = new_g + g_fwd[bni]
                                    if candidate < best:
                                        best      = candidate
                                        meet_node = bni
                                dx_ = bnx - ox
                                dy_ = bny - oy
                                if allow_diag:
                                    adx, ady = (dx_ if dx_ >= 0 else -dx_), (dy_ if dy_ >= 0 else -dy_)
                                    h_val = (adx if adx > ady else ady) + sqrt2_minus_1 * (adx if adx < ady else ady)
                                else:
                                    h_val = (dx_ if dx_ >= 0 else -dx_) + (dy_ if dy_ >= 0 else -dy_)
                                heappush(open_bwd, (new_g + h_val, bnx, bny))
                        else:
                            continue  # backward never bypasses walls
                        continue  # wall cell itself is never added to path

                    barrier_cost = 5 if (cell is not None and cell.destroyable()) else 0
                    new_g = g_ci + penalty + barrier_cost
                    if new_g >= g_bwd[ni]:
                        continue

                    came_from_bwd[ni] = ci
                    g_bwd[ni]         = new_g

                    if closed_fwd[ni]:
                        candidate = new_g + g_fwd[ni]
                        if candidate < best:
                            best      = candidate
                            meet_node = ni

                    dx_ = nx - ox
                    dy_ = ny - oy
                    if allow_diag:
                        adx, ady = (dx_ if dx_ >= 0 else -dx_), (dy_ if dy_ >= 0 else -dy_)
                        h_val = (adx if adx > ady else ady) + sqrt2_minus_1 * (adx if adx < ady else ady)
                    else:
                        h_val = (dx_ if dx_ >= 0 else -dx_) + (dy_ if dy_ >= 0 else -dy_)
                    heappush(open_bwd, (new_g + h_val, nx, ny))

        # ── path reconstruction ───────────────────────────────────────────────
        if meet_node == -1:
            print(f"[ASTAR] FAILED origin=({ox},{oy}) target=({tx},{ty})")
            return None

        if came_from_bwd[meet_node] == meet_node:
            path = self.reconstruct_path(came_from_fwd, start_i, meet_node)
        else:
            path = self.reconstruct_path_bidir(came_from_fwd, came_from_bwd, start_i, meet_node)

        barriers_crossed = sum(
            1 for pos in path._deque
            if _map[pos.y * w + pos.x] is not None
            and _map[pos.y * w + pos.x].destroyable()
        )
        print(f"[ASTAR] origin=({ox},{oy}) target=({tx},{ty}) "
              f"path_len={len(path)} barriers_crossed={barriers_crossed}")
        return path

    def debug_print_map(self, path, origin, target, walls, include_barriers=False, explored=None):
        """
        Legend:
          O  = origin       X  = target
          *  = path         B  = barrier (destroyable)
          #  = wall         f  = closed fwd only
          b  = closed bwd   +  = closed both
          .  = unvisited
        """
        path_coords = set()
        if path:
            for pos in path._deque:
                path_coords.add((pos.x, pos.y))

        explored = explored or {}
        ox, oy   = origin.x, origin.y
        tx, ty   = target.x, target.y

        print(f"    ", end="")
        for x in range(self.w):
            print(f"{x%10}", end="")
        print()

        for y in range(self.h):
            print(f"{y:3} ", end="")
            for x in range(self.w):
                i    = y * self.w + x
                cell = self.map[i]

                if (x, y) == (ox, oy):
                    ch = "O"
                elif (x, y) == (tx, ty):
                    ch = "X"
                elif (x, y) in path_coords:
                    if cell is None:
                        ch = "*"
                    elif cell.destroyable():
                        ch = "B"
                    elif not cell.passable(walls):
                        ch = "#"
                    else:
                        ch = "*"
                elif i in explored:
                    side = explored[i]
                    if cell is not None and (cell.destroyable() or not cell.passable(walls)):
                        ch = "B" if cell.destroyable() else "#"
                    elif side == 'f':
                        ch = "f"
                    elif side == 'b':
                        ch = "b"
                    else:
                        ch = "+"
                else:
                    if cell is None:
                        ch = "."
                    elif cell.destroyable():
                        ch = "B"
                    elif not cell.passable(walls):
                        ch = "#"
                    else:
                        ch = "."
                print(ch, end="")
            print()