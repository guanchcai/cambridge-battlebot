from entity_behaviour.entity_base import EBase
from cambc import Controller, Position, Environment, EntityType
from utils.constants import *
from utils.path_finder import *
from utils.helper_functions import *
import random

class Bot(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)
        self.base_position = ct.get_position(ct.get_tile_building_id(self.original_position))
        self.internal_map = [None] * (self.map_width * self.map_height)
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

        # Exploration variables
        self.unexplored = set()
        self.buckets = {}
        self.bucket_size = 16
        
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
        self.update_map()
        if self.current_target_position:
            ct.draw_indicator_line(ct.get_position(), self.current_target_position, 255, 0, 0)
        
        self.move_to_pos()

        position = ct.get_position()

        for d in DIRECTIONS:
            pos = position.add(d)
            if ct.can_place_marker(pos):
                ct.place_marker(pos, encode_coordinate(self.base_position))
                break
        
        for d in ALL_DIRECTIONS:
            pos = position.add(d)
            if ct.can_heal(pos):
                ct.heal(pos)
                break


    def update_map(self):
        self_id = self.ct.get_id()
        for tile in self.ct.get_nearby_tiles(16):
            building_id = self.ct.get_tile_building_id(tile)
            building_entity = self.ct.get_entity_type(building_id) if building_id else None
            same_team = self.ct.get_team(building_id) == self.team if building_id else True
            bot_id = self.ct.get_tile_builder_bot_id(tile)
            if bot_id == self_id:
                bot_id = None

            env = self.ct.get_tile_env(tile)
            self.set_from_pos(self.environment_map, tile, env)

            self.check_symmetry(tile, env)
            self.add_symmetry_tile(tile, env)

            if building_entity is not None and building_entity not in PASSABLE:
                env = Environment.WALL
            
            if building_entity == EntityType.CORE and not same_team:
                env = Environment.WALL

            if bot_id and self.current_state != BotState.GOING_BACK:
                env = Environment.WALL

            self.set_from_pos(self.internal_map, tile, env)

            self.update_tile(tile, building_id, bot_id)
            
            if self.get_from_pos(self.internal_map, tile) != Environment.EMPTY and self.distance_map and tile in self.distance_map and tile != self.current_target_position:
                print(f"Encountered wall in path on position: {tile}")
                self.distance_map = None

            if tile in self.unexplored:
                self.unexplored.remove(tile)
                bucket = (tile.x // self.bucket_size, tile.y // self.bucket_size)
                bucket_list = self.buckets[bucket]
                i = bucket_list.index(tile)
                bucket_list[i] = bucket_list[-1]
                bucket_list.pop()
                if not self.buckets[bucket]:
                    del self.buckets[bucket] 


    def move_to_pos(self, direction_allowed=DIRECTIONS):
        position = self.ct.get_position()

        dist_to_target = position.distance_squared(self.current_target_position)
        if dist_to_target <= self.target_distance_squared:
            self.reached_target()
        
        print(self.current_target_position)
        if not self.distance_map and self.current_target_position is not None:
            self.run_flood_fill()

        if not self.distance_map:
            print("Can't reach target from here")
            return
        
        if position == self.distance_map[0]:
            self.distance_map.popleft()
            
        if not self.distance_map:
            print("Already at target location")
            return

        move_pos = self.distance_map[0]
        build_success = self.build_road(move_pos, self.distance_map[1] if len(self.distance_map) > 1 else None)
        chosen = self.ct.get_position().direction_to(move_pos)
        if self.ct.can_move(chosen) and build_success:
            self.ct.move(chosen)
            
        if self.ct.can_destroy(position) and is_road(position, self.ct):
            self.ct.destroy(position)

        self.previous_position = position if position != self.ct.get_position() else self.previous_position

    def build_road(self, move_pos: Position, next_pos: Position):
        if self.ct.can_build_road(move_pos):
            self.ct.build_road(move_pos)
        
        return True

    def set_from_pos(self, target_list: list, pos: Position, value):
        target_list[pos.y * self.map_width + pos.x] = value

    def get_from_pos(self, target_list: list, pos: Position):
        return target_list[pos.y * self.map_width + pos.x]

    def run_flood_fill(self):
        print(f"Going from {self.ct.get_position()} to {self.current_target_position}")
        self.distance_map = self.path_finder.run(
            self.ct.get_position(),
            self.current_target_position,
            True, 
            DeltaTypes.ALL, 
            self.target_distance_squared, 
            False
        )
    
    def reached_target(self):
        if self.current_state == BotState.WANDERING:
            self.set_wandering()

    def nearest_unexplored(self) -> Position | None:
        if not self.buckets:
            return Position(random.randint(0, self.map_width - 1), random.randint(0, self.map_height - 1))
        
        pos = self.ct.get_position()

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
    
    def update_tile(self, tile: Position, building_id: int | None, bot_id: int | None):
        pass

    def check_symmetry(self, tile: Position, env: Environment):
        if self.x_axis_symmetry + self.y_axis_symmetry + self.rotational_symmetry <= 1:
            return
    
        w = self.map_width - 1
        h = self.map_height - 1
        y_axis_reflection = Position(w - tile.x, tile.y)
        x_axis_reflection = Position(tile.x, h - tile.y)
        rotation_reflection = Position(w - tile.x, h - tile.y)

        y_ref_tile = self.get_from_pos(self.environment_map, y_axis_reflection)
        x_ref_tile = self.get_from_pos(self.environment_map, x_axis_reflection)
        r_ref_tile = self.get_from_pos(self.environment_map, rotation_reflection)

        if y_ref_tile and y_ref_tile != env:
            self.y_axis_symmetry = False
        
        if x_ref_tile and x_ref_tile != env:
            self.x_axis_symmetry = False

        if r_ref_tile and r_ref_tile != env:
            self.rotational_symmetry = False
        
    def add_symmetry_tile(self, tile: Position, env: Environment):
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
        
        new_tile = False
        if self.get_from_pos(self.environment_map, ref_tile) is None:
            new_tile = True
        self.set_from_pos(self.environment_map, ref_tile, env)
        if self.get_from_pos(self.internal_map, ref_tile) is None:
            self.set_from_pos(self.internal_map, ref_tile, env)
        
        if new_tile:
            self.update_tile(ref_tile, None, None)


    def set_target(self, target_pos: Position, distance_squared: int, state: BotState):
        self.current_target_position = target_pos
        self.target_distance_squared = distance_squared
        self.current_state = state
        self.distance_map = None

    def set_wandering(self):
        self.set_target(self.base_position, 16, BotState.WANDERING)