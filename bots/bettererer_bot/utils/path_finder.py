import heapq
import math
from cambc import Controller, Position, Environment
from utils.tile_info import TileData
from utils.helper_functions import direction_to_delta
from utils.constants import DeltaTypes
from utils.path_queue import PathQueue


class AStarPathfinder:
    CPU_BUDGET_DEFAULT = 1600
    BARRIER_COST = 5

    def __init__(self, _map: list[TileData | None], w: int):
        self.map = _map
        self.w = w
        self.h = len(_map) // w
        self.area = self.w * self.h

        area = self.area

        # g-values
        self._g_fwd = [0.0] * area
        self._g_bwd = [0.0] * area

        # came-from
        self._cf_fwd = [0] * area
        self._cf_bwd = [0] * area

        # stamps
        self._stamp_gf = [0] * area
        self._stamp_gb = [0] * area
        self._stamp_cf = [0] * area   # closed forward
        self._stamp_cb = [0] * area   # closed backward

        self._call_id = 0

    # ─────────────────────────────────────────────────────────────────────
    # Index / path helpers
    # ─────────────────────────────────────────────────────────────────────

    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def reconstruct_path(self, came_from, start_i, current_i):
        w = self.w
        path = []
        ci = current_i
        while ci != start_i:
            path.append(Position(ci % w, ci // w))
            ci = came_from[ci]
        path.append(Position(start_i % w, start_i // w))
        path.reverse()
        return PathQueue(path)

    def reconstruct_path_bidir(
        self,
        came_from_fwd, stamp_cf,
        came_from_bwd, stamp_cb,
        start_i, meet_i, cid
    ):
        w = self.w
        out = []

        # forward half: start -> meet
        ci = meet_i
        while ci != start_i:
            out.append(Position(ci % w, ci // w))
            ci = came_from_fwd[ci]
        out.append(Position(start_i % w, start_i // w))
        out.reverse()

        # backward half: meet's parent -> target-side seed root
        ci = came_from_bwd[meet_i]
        while stamp_cb[ci] == cid and came_from_bwd[ci] != ci:
            out.append(Position(ci % w, ci // w))
            ci = came_from_bwd[ci]
        out.append(Position(ci % w, ci // w))

        return PathQueue(out)

    # ─────────────────────────────────────────────────────────────────────
    # Tile classification
    # class 0 = free/passable
    # class 1 = barrier (destroyable, walkable with cost)
    # class 2 = true wall (not directly walkable)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _tile_class(cell, walls) -> int:
        if cell is None:
            return 0
        if cell.passable(walls):
            return 0
        if cell.destroyable():
            return 1
        return 2

    # ─────────────────────────────────────────────────────────────────────
    # Main
    # ─────────────────────────────────────────────────────────────────────

    def run(
        self,
        origin: Position,
        target: Position,
        ignore_ores: bool,
        delta_type: DeltaTypes,
        ct: Controller,  # NEW: timing object with get_cpu_time()
        target_distance_squared: int = 0,
        bypass_wall: bool = False,        # target-zone ignore walls
        include_barriers: bool = False,   # kept for API compatibility
        cpu_budget: int = CPU_BUDGET_DEFAULT,
    ):
        # include_barriers is intentionally not changing behavior because
        # your intended semantics say barriers are walkable with a cost.
        _ = include_barriers

        start_cpu = ct.get_cpu_time_elapsed()

        w = self.w
        h = self.h
        area = self.area
        _map = self.map
        INF = math.inf

        ox, oy = origin.x, origin.y
        tx, ty = target.x, target.y
        start_i = oy * w + ox

        # Early success: already in target radius
        if (ox - tx) ** 2 + (oy - ty) ** 2 <= target_distance_squared:
            return PathQueue([Position(ox, oy)])

        walls = (
            {Environment.WALL}
            if ignore_ores
            else {Environment.WALL, Environment.ORE_TITANIUM, Environment.ORE_AXIONITE}
        )

        allow_diag = (delta_type == DeltaTypes.ALL)
        is_bridge = (delta_type == DeltaTypes.BRIDGE)

        # Movement deltas
        deltas = direction_to_delta(delta_type)
        cardinal_deltas = direction_to_delta(DeltaTypes.CARDINAL)
        normal_deltas = cardinal_deltas if is_bridge else deltas

        # Heuristic chooser
        sqrt2m1 = math.sqrt(2) - 1.0

        if allow_diag:
            def h_to_target(x, y):
                dx = x - tx
                dy = y - ty
                if dx < 0: dx = -dx
                if dy < 0: dy = -dy
                if dx > dy:
                    return dx + sqrt2m1 * dy
                return dy + sqrt2m1 * dx

            def h_to_origin(x, y):
                dx = x - ox
                dy = y - oy
                if dx < 0: dx = -dx
                if dy < 0: dy = -dy
                if dx > dy:
                    return dx + sqrt2m1 * dy
                return dy + sqrt2m1 * dx
        else:
            def h_to_target(x, y):
                dx = x - tx
                dy = y - ty
                if dx < 0: dx = -dx
                if dy < 0: dy = -dy
                return dx + dy

            def h_to_origin(x, y):
                dx = x - ox
                dy = y - oy
                if dx < 0: dx = -dx
                if dy < 0: dy = -dy
                return dx + dy

        # O(1) reset via call stamp
        self._call_id += 1
        cid = self._call_id

        g_fwd = self._g_fwd
        g_bwd = self._g_bwd
        cf_fwd = self._cf_fwd
        cf_bwd = self._cf_bwd
        stamp_gf = self._stamp_gf
        stamp_gb = self._stamp_gb
        stamp_cf = self._stamp_cf
        stamp_cb = self._stamp_cb

        # Precompute tile classes for this walls-set
        tile_cls = [0] * area
        for i in range(area):
            tile_cls[i] = self._tile_class(_map[i], walls)

        # Sanity: origin has at least one outward-expandable neighbor
        sanity_deltas = cardinal_deltas if is_bridge else deltas
        has_fwd_neighbor = False
        for ddx, ddy, _ in sanity_deltas:
            nx, ny = ox + ddx, oy + ddy
            if 0 <= nx < w and 0 <= ny < h:
                ni = ny * w + nx
                if tile_cls[ni] != 2:  # free or barrier
                    has_fwd_neighbor = True
                    break
        if not has_fwd_neighbor:
            print(f"[ASTAR] FAILED (origin surrounded) origin=({ox},{oy}) target=({tx},{ty})")
            return None

        # Sanity: target has at least one outward-expandable neighbor
        has_bwd_neighbor = False
        for ddx, ddy, _ in sanity_deltas:
            nx, ny = tx + ddx, ty + ddy
            if 0 <= nx < w and 0 <= ny < h:
                ni = ny * w + nx
                if tile_cls[ni] != 2:
                    has_bwd_neighbor = True
                    break
        if not has_bwd_neighbor:
            print(f"[ASTAR] FAILED (target surrounded) origin=({ox},{oy}) target=({tx},{ty})")
            return None

        # Forward init
        stamp_gf[start_i] = cid
        g_fwd[start_i] = 0.0
        cf_fwd[start_i] = start_i
        open_fwd = [(0.0, start_i)]

        # Track closest-forward fallback (for timeout with no meet)
        best_forward_node = start_i
        best_forward_h = h_to_target(ox, oy)

        # Backward init: seed target radius
        open_bwd = []
        r = int(math.isqrt(target_distance_squared))
        for dy in range(-r, r + 1):
            y = ty + dy
            if y < 0 or y >= h:
                continue
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > target_distance_squared:
                    continue
                x = tx + dx
                if x < 0 or x >= w:
                    continue
                ni = y * w + x

                # Seed rules:
                # - bypass_wall => always seed
                # - else seed walkable (free/barrier)
                # - always seed exact target cell
                if bypass_wall or tile_cls[ni] != 2 or (x == tx and y == ty):
                    stamp_gb[ni] = cid
                    g_bwd[ni] = 0.0
                    cf_bwd[ni] = ni
                    heapq.heappush(open_bwd, (0.0, ni))

        if not open_bwd:
            print(f"[ASTAR] FAILED (no valid landing zone) origin=({ox},{oy}) target=({tx},{ty})")
            return None

        heappush = heapq.heappush
        heappop = heapq.heappop

        best = INF
        meet_node = -1

        def timeout_return():
            nonlocal meet_node
            if meet_node != -1:
                if stamp_gb[meet_node] == cid and cf_bwd[meet_node] == meet_node:
                    return self.reconstruct_path(cf_fwd, start_i, meet_node)
                return self.reconstruct_path_bidir(
                    cf_fwd, stamp_cf, cf_bwd, stamp_cb, start_i, meet_node, cid
                )
            # no connected path yet -> closest forward partial
            if best_forward_node != -1:
                return self.reconstruct_path(cf_fwd, start_i, best_forward_node)
            return None

        # Main loop
        while open_fwd and open_bwd:
            # CPU budget check
            if ct.get_cpu_time_elapsed() - start_cpu > cpu_budget:
                path = timeout_return()
                if path is None:
                    print(f"[ASTAR] TIMEOUT no path origin=({ox},{oy}) target=({tx},{ty})")
                else:
                    print(f"[ASTAR] TIMEOUT partial path origin=({ox},{oy}) target=({tx},{ty}) len={len(path)}")
                return path

            f_fwd = open_fwd[0][0]
            f_bwd = open_bwd[0][0]

            lower = f_fwd if f_fwd < f_bwd else f_bwd
            if meet_node != -1 and lower >= best:
                break

            # Expand side with lower f; tie-break by smaller queue
            expand_forward = (f_fwd < f_bwd) or (f_fwd == f_bwd and len(open_fwd) <= len(open_bwd))

            if expand_forward:
                _, ci = heappop(open_fwd)
                if stamp_cf[ci] == cid:
                    continue
                stamp_cf[ci] = cid

                cx = ci % w
                cy = ci // w
                g_ci = g_fwd[ci]

                # meeting candidate
                if stamp_gb[ci] == cid:
                    cand = g_ci + g_bwd[ci]
                    if cand < best:
                        best = cand
                        meet_node = ci

                for ddx, ddy, step_cost in normal_deltas:
                    nx = cx + ddx
                    ny = cy + ddy
                    if nx < 0 or nx >= w or ny < 0 or ny >= h:
                        continue
                    ni = ny * w + nx
                    if stamp_cf[ni] == cid:
                        continue

                    tc = tile_cls[ni]

                    if tc == 2:
                        # true wall -> only bridge jump if bridge mode
                        if not is_bridge:
                            continue
                        # no bridge from origin
                        if cx == ox and cy == oy:
                            continue

                        for bddx, bddy, bpen in deltas:
                            bnx = cx + bddx
                            bny = cy + bddy
                            if bnx < 0 or bnx >= w or bny < 0 or bny >= h:
                                continue
                            bni = bny * w + bnx
                            if stamp_cf[bni] == cid:
                                continue

                            btc = tile_cls[bni]
                            if btc == 2:
                                continue

                            barrier_extra = self.BARRIER_COST if btc == 1 else 0
                            new_g = g_ci + bpen + barrier_extra
                            old_g = g_fwd[bni] if stamp_gf[bni] == cid else INF
                            if new_g >= old_g:
                                continue

                            cf_fwd[bni] = ci
                            g_fwd[bni] = new_g
                            stamp_gf[bni] = cid

                            # closest-forward tracking
                            bh = h_to_target(bnx, bny)
                            if bh < best_forward_h:
                                best_forward_h = bh
                                best_forward_node = bni

                            if stamp_gb[bni] == cid:
                                cand = new_g + g_bwd[bni]
                                if cand < best:
                                    best = cand
                                    meet_node = bni

                            heappush(open_fwd, (new_g + bh, bni))
                        continue

                    barrier_extra = self.BARRIER_COST if tc == 1 else 0
                    new_g = g_ci + step_cost + barrier_extra
                    old_g = g_fwd[ni] if stamp_gf[ni] == cid else INF
                    if new_g >= old_g:
                        continue

                    cf_fwd[ni] = ci
                    g_fwd[ni] = new_g
                    stamp_gf[ni] = cid

                    nh = h_to_target(nx, ny)
                    if nh < best_forward_h:
                        best_forward_h = nh
                        best_forward_node = ni

                    if stamp_gb[ni] == cid:
                        cand = new_g + g_bwd[ni]
                        if cand < best:
                            best = cand
                            meet_node = ni

                    heappush(open_fwd, (new_g + nh, ni))

            else:
                _, ci = heappop(open_bwd)
                if stamp_cb[ci] == cid:
                    continue
                stamp_cb[ci] = cid

                cx = ci % w
                cy = ci // w
                g_ci = g_bwd[ci]

                if stamp_gf[ci] == cid:
                    cand = g_ci + g_fwd[ci]
                    if cand < best:
                        best = cand
                        meet_node = ci

                for ddx, ddy, step_cost in normal_deltas:
                    nx = cx + ddx
                    ny = cy + ddy
                    if nx < 0 or nx >= w or ny < 0 or ny >= h:
                        continue
                    ni = ny * w + nx
                    if stamp_cb[ni] == cid:
                        continue

                    tc = tile_cls[ni]

                    if tc == 2:
                        if not is_bridge:
                            continue
                        # no bridge from target anchor
                        if cx == tx and cy == ty:
                            continue

                        for bddx, bddy, bpen in deltas:
                            bnx = cx + bddx
                            bny = cy + bddy
                            if bnx < 0 or bnx >= w or bny < 0 or bny >= h:
                                continue
                            bni = bny * w + bnx
                            if stamp_cb[bni] == cid:
                                continue

                            btc = tile_cls[bni]
                            if btc == 2:
                                continue

                            barrier_extra = self.BARRIER_COST if btc == 1 else 0
                            new_g = g_ci + bpen + barrier_extra
                            old_g = g_bwd[bni] if stamp_gb[bni] == cid else INF
                            if new_g >= old_g:
                                continue

                            cf_bwd[bni] = ci
                            g_bwd[bni] = new_g
                            stamp_gb[bni] = cid

                            if stamp_gf[bni] == cid:
                                cand = new_g + g_fwd[bni]
                                if cand < best:
                                    best = cand
                                    meet_node = bni

                            heappush(open_bwd, (new_g + h_to_origin(bnx, bny), bni))
                        continue

                    barrier_extra = self.BARRIER_COST if tc == 1 else 0
                    new_g = g_ci + step_cost + barrier_extra
                    old_g = g_bwd[ni] if stamp_gb[ni] == cid else INF
                    if new_g >= old_g:
                        continue

                    cf_bwd[ni] = ci
                    g_bwd[ni] = new_g
                    stamp_gb[ni] = cid

                    if stamp_gf[ni] == cid:
                        cand = new_g + g_fwd[ni]
                        if cand < best:
                            best = cand
                            meet_node = ni

                    heappush(open_bwd, (new_g + h_to_origin(nx, ny), ni))

        # Final reconstruction
        if meet_node == -1:
            # no connected path; return closest-forward partial (policy on fail)
            if best_forward_node != -1:
                path = self.reconstruct_path(cf_fwd, start_i, best_forward_node)
                print(f"[ASTAR] FAILED-CONNECT partial origin=({ox},{oy}) target=({tx},{ty}) len={len(path)}")
                return path

            print(f"[ASTAR] FAILED origin=({ox},{oy}) target=({tx},{ty})")
            return None

        if stamp_gb[meet_node] == cid and cf_bwd[meet_node] == meet_node:
            path = self.reconstruct_path(cf_fwd, start_i, meet_node)
        else:
            path = self.reconstruct_path_bidir(
                cf_fwd, stamp_cf, cf_bwd, stamp_cb, start_i, meet_node, cid
            )

        barriers_crossed = 0
        for pos in path._deque:
            i = pos.y * w + pos.x
            if tile_cls[i] == 1:
                barriers_crossed += 1

        print(
            f"[ASTAR] origin=({ox},{oy}) target=({tx},{ty}) "
            f"path_len={len(path)} barriers_crossed={barriers_crossed}"
        )
        return path

    # ─────────────────────────────────────────────────────────────────────
    # Debug map
    # ─────────────────────────────────────────────────────────────────────

    def debug_print_map(self, path, origin, target, walls, include_barriers=False, explored=None):
        """
        Legend:
          O  = origin       X  = target
          *  = path         B  = barrier (destroyable)
          #  = wall         f  = closed fwd only
          b  = closed bwd   +  = closed both.  = unvisited
        """
        _ = include_barriers

        path_coords = set()
        if path:
            for pos in path._deque:
                path_coords.add((pos.x, pos.y))

        explored = explored or {}
        ox, oy = origin.x, origin.y
        tx, ty = target.x, target.y

        print("    ", end="")
        for x in range(self.w):
            print(f"{x % 10}", end="")
        print()

        for y in range(self.h):
            print(f"{y:3} ", end="")
            for x in range(self.w):
                i = y * self.w + x
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