import heapq
import math
import random
from cambc import Controller, EntityType, Position, Environment
from utils.tile_info import TileData
from utils.helper_functions import direction_to_delta
from utils.constants import DeltaTypes, PathfindStatus
from utils.path_queue import PathQueue

class AStarPathfinder:
    HEURISTIC_MULTIPLIER = 1.5

    def __init__(self, _map: list[TileData | None], w: int):
        self.map = _map
        self.w = w
        self.h = len(_map) // w
        self.area = self.w * self.h
        self.ct = None
        self._cache = None

    def heuristic(self, i1, i2):
        y1, x1 = divmod(i1, self.w)
        y2, x2 = divmod(i2, self.w)
        return self.HEURISTIC_MULTIPLIER * ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
    
    def index_of(self, x, y):
        return y * self.w + x
    
    def get_penalty(self, index, team, bot_id, bridge_allowed):
        tile = self.map[index]
        if tile is None:
            return 1
        if tile.destroyable():
            return 5
        if tile.passable(self.ct):
            return 0
        if tile.bot_id == bot_id:
            return 0
        if tile.bot_team == team:
            if bridge_allowed or (bot_id < tile.bot_id and tile.building_type != EntityType.CORE) and random.random() > 0.8:
                return 0
        return math.inf
    
    def add_to_id(self, index, delta_x, delta_y):
        col = index % self.w
        new_col = col + delta_x
        if new_col < 0 or new_col >= self.w: 
            return
        cand_id = index + delta_x + delta_y * self.w
        if cand_id < 0 or cand_id >= self.area:
            return
        return cand_id
    
    def run(
        self, 
        start: Position, 
        goal: Position,
        distance_squared: int,
        ct: Controller,
        bridge_allowed = False
    ):
        print(f"Running path find from {start}, to {goal}")
        bot_id = ct.get_id()
        team = ct.get_team()
        self.ct = ct
        
        index_start = self.index_of(start.x, start.y)
        index_goal = self.index_of(goal.x, goal.y)

        c = self._cache
        if (
            c is not None
            and c["index_start"]      == index_start
            and c["index_goal"]       == index_goal
            and c["bridge_allowed"]   == bridge_allowed
            and c["distance_squared"] == distance_squared
        ):
            # Restore search state
            open_f           = c["open_f"]
            open_b           = c["open_b"]
            g_f              = c["g_f"]
            g_b              = c["g_b"]
            parent_f         = c["parent_f"]
            parent_b         = c["parent_b"]
            mu               = c["mu"]
            meet             = c["meet"]
            best_f_node_index = c["best_f_node_index"]
            best_f_score     = c["best_f_score"]
            print("Resuming pathfind...")
        else:
            open_f = []
            best_f_node_index = None
            best_f_score = math.inf

            open_b = []
            
            g_f = [math.inf] * self.area
            parent_f = [None] * self.area
            g_b = [math.inf] * self.area
            parent_b = [None] * self.area

            mu = math.inf # Best cost to reach the goal found so far
            meet = None # Index of the connecting node that reaches the goal found so far

            heapq.heappush(open_f, (self.heuristic(index_start, index_goal), index_start))
            g_f[index_start] = 0.0
            heapq.heappush(open_b, (self.heuristic(index_start, index_goal), index_goal))
            g_b[index_goal] = 0.0

            radius = int(distance_squared ** 0.5)
            y0 = max(0, goal.y - radius)
            y1 = min(self.h - 1, goal.y + radius)

            for y in range(y0, y1 + 1):
                dy = y - goal.y
                x0 = max(0, goal.x - radius)
                x1 = min(self.w - 1, goal.x + radius)

                for x in range(x0, x1 + 1):
                    dx = x - goal.x
                    if dx * dx + dy * dy > distance_squared:
                        continue
                        
                    index = self.index_of(x, y)
                    if index == index_start:
                        continue
                    if index != index_goal and not (self.map[index] is None or self.map[index].passable(self.ct) or self.map[index].bot_id == bot_id or self.map[index].destroyable()):
                        continue

                    penalty = self.get_penalty(index, team, bot_id, bridge_allowed)
                    if math.isinf(penalty):
                        continue

                    g_b[index] = penalty
                    heapq.heappush(open_b, (self.heuristic(index, index_start) + penalty, index))
        
        while open_f and open_b and ct.get_cpu_time_elapsed() < 1900:
            # termination (after you already have some candidate)
            if math.isfinite(mu) and g_f[open_f[0][1]] + g_b[open_b[0][1]] >= mu:
                break

            if open_f[0][0] <= open_b[0][0]:
                f_u, u = heapq.heappop(open_f)
                
                if abs(f_u - (g_f[u] + self.heuristic(u, index_goal))) > 1e-9:
                    continue

                if math.isfinite(g_b[u]):
                    cand = g_f[u] + g_b[u]
                    if cand < mu:
                        mu = cand
                        meet = u

                if u != index_start:
                    combined = g_f[u] + 2 * self.heuristic(u, index_goal)
                    if combined < best_f_score:
                        best_f_score = combined
                        best_f_node_index = u
                
                nbrs = direction_to_delta(DeltaTypes.CARDINAL) if bridge_allowed else direction_to_delta(DeltaTypes.ALL)
                build_bridge = False
                for v in nbrs:
                    next_index = self.add_to_id(u, v[0], v[1])
                    if next_index is None:
                        continue

                    penalty = self.get_penalty(next_index, team, bot_id, bridge_allowed)
                    if math.isinf(penalty):
                        if bridge_allowed:
                            build_bridge = True
                        continue

                    ng = g_f[u] + penalty + v[2]
                    if ng < g_f[next_index]:
                        g_f[next_index] = ng
                        parent_f[next_index] = u
                        heapq.heappush(open_f, (ng + self.heuristic(next_index, index_goal), next_index))

                        if math.isfinite(g_b[next_index]):
                            cand = g_f[next_index] + g_b[next_index]
                            if cand < mu:
                                mu = cand
                                meet = next_index
                
                if u != index_start and build_bridge:
                    for v in direction_to_delta(DeltaTypes.BRIDGE):
                        next_index = self.add_to_id(u, v[0], v[1])
                        if next_index is None:
                            continue

                        penalty = self.get_penalty(next_index, team, bot_id, bridge_allowed)
                        if math.isinf(penalty):
                            continue

                        ng = g_f[u] + penalty + v[2]
                        if ng < g_f[next_index]:
                            g_f[next_index] = ng
                            parent_f[next_index] = u
                            heapq.heappush(open_f, (ng + self.heuristic(next_index, index_goal), next_index))
                            
                            if math.isfinite(g_b[next_index]):
                                cand = g_f[next_index] + g_b[next_index]
                                if cand < mu:
                                    mu = cand
                                    meet = next_index
                
            else:
                b_u, u = heapq.heappop(open_b)
                
                if abs(b_u - (g_b[u] + self.heuristic(u, index_start))) > 1e-9:
                    continue

                if math.isfinite(g_f[u]):
                    cand = g_f[u] + g_b[u]
                    if cand < mu:
                        mu = cand
                        meet = u
                
                nbrs = direction_to_delta(DeltaTypes.CARDINAL) if bridge_allowed else direction_to_delta(DeltaTypes.ALL)
                build_bridge = False
                for v in nbrs:
                    next_index = self.add_to_id(u, v[0], v[1])
                    if next_index is None:
                        continue

                    penalty = self.get_penalty(next_index, team, bot_id, bridge_allowed)
                    if math.isinf(penalty):
                        if bridge_allowed:
                            build_bridge = True
                        continue

                    ng = g_b[u] + penalty + v[2]
                    if ng < g_b[next_index]:
                        g_b[next_index] = ng
                        parent_b[next_index] = u
                        heapq.heappush(open_b, (ng + self.heuristic(next_index, index_start), next_index))

                        if math.isfinite(g_f[next_index]):
                            cand = g_f[next_index] + g_b[next_index]
                            if cand < mu:
                                mu = cand
                                meet = next_index
                
                if build_bridge:
                    for v in direction_to_delta(DeltaTypes.BRIDGE):
                        next_index = self.add_to_id(u, v[0], v[1])
                        if next_index is None:
                            continue

                        penalty = self.get_penalty(next_index, team, bot_id, bridge_allowed)
                        if math.isinf(penalty) or next_index == index_start:
                            continue
                        
                        ng = g_b[u] + penalty + v[2]
                        if ng < g_b[next_index]:
                            g_b[next_index] = ng
                            parent_b[next_index] = u
                            heapq.heappush(open_b, (ng + self.heuristic(next_index, index_start), next_index))
                            
                            if math.isfinite(g_f[next_index]):
                                cand = g_f[next_index] + g_b[next_index]
                                if cand < mu:
                                    mu = cand
                                    meet = next_index
            
            if ct.get_cpu_time_elapsed() >= 1900:
                self._save_cache(
                    index_start, index_goal, distance_squared, bridge_allowed,
                    open_f, open_b, g_f, g_b, parent_f, parent_b,
                    mu, meet, best_f_node_index, best_f_score
                )
                break
        # 1) full path found
        if meet is not None and math.isfinite(mu):
            print("Path found")
            path_idx = self._reconstruct_bidirectional(meet, parent_f, parent_b)
            return (PathfindStatus.SUCCESS, PathQueue(self._indices_to_positions(path_idx)))

        # 2) timed out -> fallback to best forward reached
        if open_b and open_f and best_f_node_index is not None:
            print(f"Fallback to best forward reached {(lambda a: (a[1], a[0]))(divmod(best_f_node_index, self.w))}")
            return (PathfindStatus.TIMEOUT, None)

        # 3) forward exhausted (or nothing useful)
        if not open_f:
            print("Fallback to forward exhausted")
            return (PathfindStatus.FAILURE, None)
        elif not open_b:
            print("Fallback to backward exhausted")
            return (PathfindStatus.FAILURE, None)
        
        return (PathfindStatus.FAILURE, None)
    
    def _reconstruct_forward(self, end_idx, parent_f):
        path = []
        cur = end_idx
        while cur is not None:
            path.append(cur)
            cur = parent_f[cur]
        path.reverse()
        return path

    def _reconstruct_bidirectional(self, meet, parent_f, parent_b):
        # start -> meet
        left = self._reconstruct_forward(meet, parent_f)

        # meet -> backward source (goal-radius seed)
        right = []
        cur = parent_b[meet]
        while cur is not None:
            right.append(cur)
            cur = parent_b[cur]

        return left + right

    def _indices_to_positions(self, path_idx):
        out = []
        for idx in path_idx:
            y, x = divmod(idx, self.w)
            out.append(Position(x, y))
        return out
    
    def _save_cache(self, index_start, index_goal, distance_squared, bridge_allowed,
                open_f, open_b, g_f, g_b, parent_f, parent_b,
                mu, meet, best_f_node_index, best_f_score):
        self._cache = {
            "index_start": index_start, "index_goal": index_goal,
            "distance_squared": distance_squared, "bridge_allowed": bridge_allowed,
            "open_f": open_f, "open_b": open_b,
            "g_f": g_f, "g_b": g_b,
            "parent_f": parent_f, "parent_b": parent_b,
            "mu": mu, "meet": meet,
            "best_f_node_index": best_f_node_index, "best_f_score": best_f_score,
        }