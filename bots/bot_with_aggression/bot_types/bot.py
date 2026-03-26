from enum import Enum
from player_utils import *
from collections import defaultdict
from path_finder_two import flood_fill
from abc import ABC, abstractmethod

class BOT_STATE(Enum):
    WALKING_BACK = 1
    WANDERING = 2
    GOING_TO_TARGET = 3
    BOMBER = 4

class Bot(ABC):
    def __init__(self, ct: Controller):
        # Bot info
        self.current_state = BOT_STATE.WANDERING
        self.dementia_rate = 0.99
        self.enemy_pos = None
        self.home_pos = None
        self.original_pos = None

        self.other_potential_enemy_base_pos = []

        # Path finding variables
        self.internal_map = None
        self.internal_walkable_map = None
        self.target_distance_squared = 0    
        self.map_width = ct.get_map_width()    
        
        self.distance_map = None
        self.current_target_pos = None
        self.previous_target_pos = None

        # Exploration variables
        self.unexplored = set()
        self.buckets = {}
        self.bucket_size = 16

        self._initialisation(ct)
        
    @abstractmethod
    def _initialisation(self, ct: Controller):
        position = ct.get_position()
        map_width = ct.get_map_width()
        map_height = ct.get_map_height()
        core_center = ct.get_position(ct.get_tile_building_id(position))
        self.original_pos = core_center or position
        
        self.enemy_pos = Position(map_width - self.original_pos.x - 1, map_height - self.original_pos.y - 1)
        self.other_potential_enemy_base_pos = [
            Position(self.original_pos.x, map_height - self.original_pos.y - 1), 
            Position(map_width - self.original_pos.x - 1, self.original_pos.y)
        ]

        self.internal_map = [None] * (map_width * map_height)
        self.internal_walkable_map = [None] * (map_width * map_height)
        for x in range(map_width):
            for y in range(map_height):
                p = Position(x, y)
                self.unexplored.add(p)
                bucket = (x // self.bucket_size, y // self.bucket_size)
                if bucket not in self.buckets:
                    self.buckets[bucket] = []
                self.buckets[bucket].append(p)
        

    @abstractmethod
    def _set_wandering(self):
        self.current_state = BOT_STATE.WANDERING
        self.current_target_pos = None
        self.previous_target_pos = None
        self.target_distance_squared = 16
        self.distance_map = None

    @abstractmethod
    def _set_internal_map(self, position: Position):
        self.distance_map = flood_fill(
            self.internal_walkable_map,
            self.map_width,
            self.current_target_pos,
            position, 
            ignore_ores=True,
            target_distance_squared=self.target_distance_squared,
            allow_diagonal=True,
            bypass_wall=False
        )
        
    @abstractmethod
    def _move_to_pos(self, ct: Controller, allowed_movements=DIRECTIONS):
        if not self.current_target_pos:
            return
        position = ct.get_position()

        dist_to_target = position.distance_squared(self.current_target_pos)
        if dist_to_target <= self.target_distance_squared:
            self._target_reached(ct)
            return
        
        if self.previous_target_pos != self.current_target_pos or self.distance_map is None:
            self.previous_target_pos = self.current_target_pos
            self._set_internal_map(position)

        decisions = [d for d in
                     allowed_movements
                     if is_in_bound(position.add(d), ct)]
        
        chosen = min(decisions, key=lambda d: get_from_dir(self.distance_map, position, d, self.map_width))
        move_pos = position.add(chosen)
        reachable = [d for d in decisions
                    if get_from_dir(self.distance_map, position, d, self.map_width) not in (None, math.inf)]

        if not reachable:
            # Target is unreachable from here, abandon it
            self._set_wandering()
            return

        next_decisions = [d for d in allowed_movements
                  if is_in_bound(move_pos.add(d), ct)]
        next_chosen = min(next_decisions, key=lambda d: get_from_dir(self.distance_map, move_pos, d, self.map_width))

        self._build_road(ct, move_pos, next_chosen)
        if ct.can_move(chosen):
            ct.move(chosen)
        else:
            self._hit_wall(move_pos, ct)

    @abstractmethod
    def _build_road(self, ct: Controller, move_pos: Position, next_direction: Direction | None=None):
        pass

    def update_map(self, ct: Controller):
        w = ct.get_map_width()
        for tile in ct.get_nearby_tiles():
            env = ct.get_tile_env(tile)
            envp = env
            building_id = ct.get_tile_building_id(tile)

            if building_id and ct.get_entity_type(building_id) == EntityType.CORE and ct.get_team(building_id) != ct.get_team():
                # Check the enemy core position
                if ct.get_position(building_id) != self.enemy_pos:
                    # Our initial guess is wrong
                    self.enemy_pos = ct.get_position(building_id)
            elif tile == self.enemy_pos and not (building_id and ct.get_entity_type(building_id) == EntityType.CORE):
                # Our initial guess is wrong
                self.enemy_pos = self.other_potential_enemy_base_pos.pop()

            if building_id is not None:
                same_team = ct.get_team(building_id) == ct.get_team()
                etype = ct.get_entity_type(building_id)
                if etype not in PASSABLE:
                    env = Environment.WALL
                    envp = env
                
                if etype == EntityType.MARKER and same_team:
                    env = Environment.WALL
                    envp = env
                    self._read_markers(ct.get_marker_value(building_id), tile)

                if not same_team:
                    env = Environment.WALL
                    if etype == EntityType.CORE:
                        envp = Environment.WALL
                
            self._update_tile(tile, building_id, ct)

            set_from_pos(self.internal_map, tile, env, w)
            set_from_pos(self.internal_walkable_map, tile, envp, w)
            
            if tile in self.unexplored:
                self.unexplored.remove(tile)
                bucket = (tile.x // self.bucket_size, tile.y // self.bucket_size)
                self.buckets[bucket].remove(tile)
                if not self.buckets[bucket]:
                    del self.buckets[bucket]  # prune empty buckets
    
    @abstractmethod
    def _read_markers(self, val: int, marker_pos: Position):
        pass

    @abstractmethod
    def _find_target(self, ct: Controller):
        pass

    @abstractmethod
    def _hit_wall(self, wall_pos: Position, ct: Controller):
        self.distance_map = None  # hit a real wall, repath

    @abstractmethod
    def _update_tile(self, tile: Position, building_id: int | None, ct: Controller):
        pass

    def _nearest_unexplored(self, pos: Position) -> Position | None:
        if not self.buckets:
            return None

        bx, by = pos.x // self.bucket_size, pos.y // self.bucket_size

        # Find the closest bucket by Chebyshev distance, break ties randomly
        best_bucket = min(
            self.buckets.keys(),
            key=lambda b: (max(abs(b[0] - bx), abs(b[1] - by)), random.random())
        )

        return min_with_random_tiebreak(
            self.buckets[best_bucket],
            key=lambda c: pos.distance_squared(c)
        )

    @abstractmethod
    def _target_reached(self, ct: Controller):
        pass

    def _pick_random(self, ct: Controller, allowed_directions=DIRECTIONS):
        print("Picking random!")
        pos = ct.get_position()
        move_dir = random.choice([d for d in allowed_directions if ct.is_tile_empty(pos.add(d))])
        self._build_road(ct, pos.add(move_dir))
        ct.move(move_dir)

    def print_distance_map(self):
        def cell_to_str(c) -> str:
            if c is None:
                return "__"
            if math.isinf(c):
                return "██"
            return f"{math.ceil(c):02d}"

        h = len(self.distance_map) // self.map_width
        for y in range(h):
            row = self.distance_map[y * self.map_width : (y + 1) * self.map_width]
            print("".join(cell_to_str(c) for c in row))
    def print_map(self):
        h = len(self.internal_map) // self.map_width
        for y in range(h):
            row = self.internal_map[y * self.map_width : (y + 1) * self.map_width]
            print("".join("██" if cell == Environment.WALL else "  " for cell in row))