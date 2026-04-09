from entity_behaviour.entity_base import EBase
from cambc import Controller, Position, Environment, EntityType
from utils.constants import *
from utils.path_finder import *
from utils.helper_functions import *
from utils.tile_info import TileData
import math
import random

from itertools import product

class Bot(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
        self.base_position = ct.get_position(ct.get_tile_building_id(self.original_position))
        self.internal_map: list[TileData | None] = [None] * (self.map_width * self.map_height)
        self.environment_map = [None] * (self.map_width * self.map_height)

        self.ore_sites = set()
        self.visited_ore_sites = set()
        self.team = ct.get_team()
        self.current_target_position = self.ct.get_position()
        self.target_distance_squared = 0
        self.distance_map = None
        self.current_state = BotState.WANDERING
        self.previous_position = None
        self.path_finder = AStarPathfinder(self.internal_map, self.map_width)
        
        self.x_axis_symmetry = True
        self.y_axis_symmetry = True
        self.rotational_symmetry = True

        self.enemy_base_pos = None
        self.enemy_launchers = set()

        # Exploration variables
        self.unexplored = set()
        self.buckets = {}
        self.bucket_size = 16

        self.position = ct.get_position()

        self.bum_factor = 0.5 # 0 to 1

        for x in range(self.map_width):
            for y in range(self.map_height):
                p = Position(x, y)
                self.unexplored.add(p)
                bucket = (x // self.bucket_size, y // self.bucket_size)
                if bucket not in self.buckets:
                    self.buckets[bucket] = []
                self.buckets[bucket].append(p)

    def run_tick(self, ct: Controller):
        self.ct = ct
        self.position = ct.get_position()
        print(f"开始计时 {ct.get_cpu_time_elapsed()}")
        self.move_to_pos()
        print(f"计时 ended {ct.get_cpu_time_elapsed()}")
        print(f"Time left to diddle {self.ct.get_cpu_time_elapsed()}")
        self.update_map()
        if self.current_target_position:
            ct.draw_indicator_line(ct.get_position(), self.current_target_position, 255, 0, 0)

        for d in ALL_DIRECTIONS:
            pos = self.position.add(d)
            if ct.can_place_marker(pos):
                ct.place_marker(pos, encode_coordinate(self.base_position, self.x_axis_symmetry, self.y_axis_symmetry, self.rotational_symmetry))
        
            if ct.can_heal(self.position):
                ct.heal(self.position)


    def update_map(self):
        for t in self.ct.get_nearby_tiles():
            # Store all tile data
            building_id = self.ct.get_tile_building_id(t)
            building_entity = self.ct.get_entity_type(building_id) if building_id else None
            same_team = self.ct.get_team(building_id) == self.team if building_id else None
            bot_id = self.ct.get_tile_builder_bot_id(t)
            bot_team = self.ct.get_team(bot_id) if bot_id else None
            env = self.ct.get_tile_env(t)

            tile = TileData(env, building_id, building_entity, same_team, bot_id, bot_team)

            self.check_symmetry(t, tile)
            self.add_symmetry_tile(t, tile)
            
            if not self.enemy_base_pos and building_entity == EntityType.CORE and not same_team:
                self.enemy_base_pos = self.ct.get_position(building_id)

            self.set_from_pos(t, tile)

            if building_entity == EntityType.LAUNCHER and not same_team:
                self.enemy_launchers.add(tile)
                
            print(f"Time before update tile: {self.ct.get_cpu_time_elapsed()}")
            self.update_tile(t, tile)
            print(f"Time after update tile: {self.ct.get_cpu_time_elapsed()}")
            if not ((tile.passable() or tile.bot_id == self.id) or (t == self.current_target_position and tile.destroyable())) and self.distance_map and t in self.distance_map:
                print(f"Encountered wall at {t}")
                print(tile.building_type)
                print(self.get_from_pos(t).destroyable())
                self.distance_map = None

            self.unexplored.discard(t)
            bucket_key = (t.x // self.bucket_size, t.y // self.bucket_size)
            bucket_list = self.buckets.get(bucket_key)
            if bucket_list:
                try:
                    i = bucket_list.index(t)
                    bucket_list[i] = bucket_list[-1]
                    bucket_list.pop()
                except ValueError:
                    pass
                if not bucket_list:
                    del self.buckets[bucket_key]
            
        for launcher_pos in self.enemy_launchers:
            for dx, dy in product(range(-1,2), repeat=2):
                if dx * dx + dy * dy <= TURRET_THREAT_RADIUS:
                    wall_pos = Position(launcher_pos.x + dx, launcher_pos.y + dy)
                    if is_in_bound(wall_pos, self.ct):
                        pos = self.get_from_pos(self.internal_map, wall_pos)
                        if pos is not None:
                            pos.covered_by_enemy = True
                            if pos in self.distance_map:
                                self.distance_map = None

    def move_to_pos(self):
        if self.current_target_position is None:
            print("How molestable")
            return
        dist_to_target = self.position.distance_squared(self.current_target_position)
        already_reached = False
        if dist_to_target <= self.target_distance_squared:
            self.reached_target()
            already_reached = True
        
        print(f"Path find started at {self.ct.get_cpu_time_elapsed()}")
        if not self.distance_map and self.current_target_position is not None:
            self.run_flood_fill()
        print(f"Path find ended at {self.ct.get_cpu_time_elapsed()}")
        if self.distance_map is None:
            print(f"Can't reach Epstein's island at {self.current_target_position} from {self.position}")
            self.unreachable_path()
            return
        
        if self.position == self.distance_map[0]:
            self.distance_map.popleft()
        
        if not self.distance_map:
            print("Already at Epstein's island")
            return

        move_pos = self.distance_map[0]
        
        print(f"Build road start {self.ct.get_cpu_time_elapsed()}")
        build_success = self.build_road(move_pos, self.distance_map[1] if len(self.distance_map) > 1 else None)
        chosen = self.position.direction_to(move_pos)
        print(f"Build road finish {self.ct.get_cpu_time_elapsed()}")
        if self.ct.can_move(chosen) and build_success:
            self.ct.move(chosen)
            self.previous_position = self.position if self.previous_position != self.position else self.previous_position
        
        tile_data = self.get_from_pos(self.position)
        if self.ct.get_current_round() < 50 and tile_data and tile_data.is_team_road() and self.ct.can_destroy(self.position):
            self.ct.destroy(self.position)

        new_pos = self.ct.get_position() 
        if not already_reached and new_pos.distance_squared(self.current_target_position) <= self.target_distance_squared:
            print("Reached position after moving")
            self.reached_target()


    def build_road(self, move_pos: Position, next_pos: Position):
        move_pos_data = self.get_from_pos(move_pos)
        if move_pos_data and move_pos_data.destroyable() and self.ct.can_destroy(move_pos):
            self.ct.destroy(move_pos)
        if self.ct.can_build_road(move_pos):
            self.ct.build_road(move_pos)
        
        return True
    
    def unreachable_path(self):
        self.set_wandering()

    def set_from_pos(self, pos: Position, value):
        self.internal_map[pos.y * self.map_width + pos.x] = value

    def get_from_pos(self, pos: Position) -> TileData | None:
        return self.internal_map[pos.y * self.map_width + pos.x]

    def run_flood_fill(self):
        print(f"Going from {self.position} to {self.current_target_position}")
        self.distance_map = self.path_finder.run(
            self.position,
            self.current_target_position,
            True, 
            DeltaTypes.ALL, 
            self.target_distance_squared, 
            False
        )
    
    def reached_target(self):
        self.set_wandering()

    def score_tile(self, tile: Position, wrt_enemy_base=False):
        dist_to_self = self.position.distance_squared(tile)
        dist_to_base = self.base_position.distance_squared(tile) if not wrt_enemy_base else self.enemy_base_pos.distance_squared(tile)
        return self.bum_factor * dist_to_self + (1-self.bum_factor) * dist_to_base

    def nearest_unexplored(self) -> Position | None:
        # best_tile = min(self.unexplored, key=lambda t: self.score_tile(t), default=None)
        # return best_tile
        # return Position(random.randint(0, self.map_width - 1), random.randint(0, self.map_height - 1))
        
        if not self.buckets:
            return Position(random.randint(0, self.map_width - 1), random.randint(0, self.map_height - 1))

        bx, by = self.position.x // self.bucket_size, self.position.y // self.bucket_size

        # Find the closest bucket by Chebyshev distance, break ties randomly

        # best_bucket = min(
        #     self.buckets.keys(),
        #     key=lambda b: (max(abs(b[0] - bx), abs(b[1] - by)), random.random())
        # )
        best_bucket = min(
            self.buckets.keys(),
            key=lambda b: (self.score_tile(Position(
                b[0] * self.bucket_size + self.bucket_size // 2,
                b[1] * self.bucket_size + self.bucket_size // 2
            )), random.random())
        )

        return min_with_random_tiebreak(
            self.buckets[best_bucket],
            key=lambda c: self.position.distance_squared(c)
        )

    
    def update_tile(self, tile: Position, tile_data: TileData):
        pass

    def check_symmetry(self, tile: Position, tile_data: TileData):
        if self.x_axis_symmetry + self.y_axis_symmetry + self.rotational_symmetry <= 1:
            return
    
        w = self.map_width - 1
        h = self.map_height - 1
        y_axis_reflection = Position(w - tile.x, tile.y)
        x_axis_reflection = Position(tile.x, h - tile.y)
        rotation_reflection = Position(w - tile.x, h - tile.y)

        y_ref_tile = self.get_from_pos(y_axis_reflection)
        x_ref_tile = self.get_from_pos(x_axis_reflection)
        r_ref_tile = self.get_from_pos(rotation_reflection)

        if y_ref_tile and y_ref_tile.environment != tile_data.environment:
            self.y_axis_symmetry = False
        
        if x_ref_tile and x_ref_tile.environment != tile_data.environment:
            self.x_axis_symmetry = False

        if r_ref_tile and r_ref_tile.environment != tile_data.environment:
            self.rotational_symmetry = False
        
        if self.map_width % 2 == 1 and self.base_position.x == self.map_width // 2:
            self.x_axis_symmetry = True
            self.rotational_symmetry = False
            self.y_axis_symmetry = False

        if self.map_height % 2 == 1 and self.base_position.y == self.map_height // 2:
            self.y_axis_symmetry = True
            self.rotational_symmetry = False
            self.x_axis_symmetry = False
        
    def add_symmetry_tile(self, tile: Position, tile_data: TileData):
        if self.x_axis_symmetry + self.y_axis_symmetry + self.rotational_symmetry != 1:
            return
        
        w = self.map_width - 1
        h = self.map_height - 1
        
        if self.y_axis_symmetry:
            ref_tile = Position(w - tile.x, tile.y)
            self.enemy_base_pos = Position(w - self.base_position.x, self.base_position.y)
            
        if self.x_axis_symmetry:
            ref_tile = Position(tile.x, h - tile.y)
            self.enemy_base_pos = Position(self.base_position.x, h - self.base_position.y)
            
        if self.rotational_symmetry:
            ref_tile = Position(w - tile.x, h - tile.y)
            self.enemy_base_pos = Position(w - self.base_position.x, h - self.base_position.y)
        
        if self.get_from_pos(ref_tile) is None:
            tile_data = TileData(tile_data.environment)
            self.set_from_pos(ref_tile, tile_data)
            self.update_tile(ref_tile, tile_data)

    def set_target(self, target_pos: Position, distance_squared: int, state: BotState):
        self.current_target_position = target_pos
        self.target_distance_squared = distance_squared
        self.current_state = state
        self.distance_map = None

    def set_wandering(self):
        self.set_target(self.base_position, 16, BotState.WANDERING)

    def move_to_adjacent(self, directions_allowed=DIRECTIONS):
        candidate = []
        for d in directions_allowed:
            check_pos = self.position.add(d)
            check_data = self.get_from_pos(check_pos)
            if not checkable_position(check_pos, self.ct):
                continue
            if check_data and check_data.environment != Environment.WALL:
                if self.ct.can_move(d):
                    self.ct.move(d)
                    return
            if self.ct.is_tile_empty(check_pos):
                candidate = check_pos
        
        if candidate:
            if self.ct.can_build_road(candidate):
                self.ct.build_road(candidate)
            if self.ct.can_move(d):
                self.ct.move(d)
    
    def handle_thrown(self):
        pass

    def is_passable(self, tile: Position):
        if not checkable_position(tile, self.ct):
            return False
        to_check = self.get_from_pos(tile)
        return to_check is None or to_check.bot_id == self.id or to_check.passable() or to_check.destroyable()
        
    def get_positions_of_entities(self, origin, radius_sq, entity_type, team):
        results = []
        radius = int(radius_sq ** 0.5)  # bounding box side
        ox, oy = (origin.x, origin.y)

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx*dx + dy*dy > radius_sq:
                    continue  # outside circle, skip
                pos = Position(ox + dx, oy + dy)
                if not checkable_position(pos, self.ct):
                    continue
                tile_data = self.get_from_pos(pos)
                if tile_data and tile_data.building_type == entity_type and tile_data.own_team:
                    results.append(pos)
        return results
