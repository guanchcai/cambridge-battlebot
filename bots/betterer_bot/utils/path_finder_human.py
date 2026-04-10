import heapq
import math
from cambc import Controller, Position, Environment
from utils.tile_info import TileData
from utils.helper_functions import direction_to_delta
from utils.constants import DeltaTypes
from utils.path_queue import PathQueue

class AStarPathfinder:
    def __init__(self, _map: list[TileData | None], w: int):
        self.map = _map
        self.w = w
        self.h = len(_map) // w
        self.area = self.w * self.h

        area = self.area

    def heuristic(self, i1, i2):
        y1, x1 = divmod(i1, self.w)
        y2, x2 = divmod(i2, self.w)
        return abs(x1 - x2) + abs(y1 - y2)
    
    def index_of(self, x, y):
        return y * self.w + x
    
    def get_penalty(self, index, team):
        if self.map[index] is None:
            return 1
        if self.map[index].destroyable():
            return 10
        if self.map[index].passable() or self.map[index].bot_team == team:
            return 1
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
        bot_id = ct.get_id()

        open_f = []
        best_f_node_index = None

        open_b = []
        
        g_f = [math.inf] * self.area
        parent_f = [None] * self.area
        g_b = [math.inf] * self.area
        parent_b = [None] * self.area

        mu = math.inf # Best cost to reach the goal found so far
        meet = None # Index of the connecting node that reaches the goal found so far

        index_start = self.index_of(start.x, start.y)
        index_goal = self.index_of(goal.x, goal.y)

        heapq.heappush(open_f, (self.heuristic(index_start, index_goal), index_start))
        g_f[index_start] = 0.0

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
                    return PathQueue([start])
                if index != index_goal and not (self.map[index] is None or self.map[index].passable() or self.map[index].bot_id == bot_id or self.map[index].destroyable()):
                    continue

                g_b[index] = 0.0
                heapq.heappush(open_b, (self.heuristic(index, index_start), index))

        while open_f and open_b and ct.get_cpu_time_elapsed() < 1900:
            # termination (after you already have some candidate)
            if math.isfinite(mu) and open_f[0][0] + open_b[0][0] >= mu:
                break

            if open_f[0][0] <= open_b[0][0]:
                f_u, u = heapq.heappop(open_f)
                
                if abs(f_u - (g_f[u] + self.heuristic(u, index_goal))) > 1e-2:
                    continue

                if math.isfinite(g_b[u]):
                    cand = g_f[u] + g_b[u]
                    if cand < mu:
                        mu = cand
                        meet = u

                if best_f_node_index is None or self.heuristic(u, index_goal) < self.heuristic(best_f_node_index, index_goal):
                    best_f_node_index = u
                
                nbrs = direction_to_delta(DeltaTypes.CARDINAL) if bridge_allowed else direction_to_delta(DeltaTypes.ALL)
                build_bridge = False
                for v in nbrs:
                    next_index = self.add_to_id(u, v[0], v[1])
                    if next_index is None:
                        continue

                    penalty = self.get_penalty(next_index, bot_id)
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

                        penalty = self.get_penalty(next_index, bot_id)
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
                
                if abs(b_u - (g_b[u] + self.heuristic(u, index_start))) > 1e-2:
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

                    penalty = self.get_penalty(next_index, bot_id)
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

                        penalty = self.get_penalty(next_index, bot_id)
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
        # 1) full path found
        if meet is not None and math.isfinite(mu):
            print("Path found")
            path_idx = self._reconstruct_bidirectional(meet, parent_f, parent_b)
            return PathQueue(self._indices_to_positions(path_idx))

        # 2) timed out -> fallback to best forward reached
        if open_b and open_f and best_f_node_index is not None and math.isfinite(g_f[best_f_node_index]):
            print("Fallback to best forward reached")
            path_idx = self._reconstruct_forward(best_f_node_index, parent_f)
            return PathQueue(self._indices_to_positions(path_idx))

        # 3) forward exhausted (or nothing useful)
        if not open_f:
            print("Fallback to forward exhausted")
        elif not open_b:
            print("Fallback to backward exhausted")
        return None
    
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