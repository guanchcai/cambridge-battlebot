import random
import math
from enum import Enum
from cambc import Controller, Direction, EntityType, Environment, Position
from path_finder import flood_fill, get_cardinal
import time
# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]
CARDINAL_DIRECTIONS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
PASSABLE = [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ROAD, EntityType.ARMOURED_CONVEYOR, EntityType.BUILDER_BOT, EntityType.CORE, EntityType.MARKER]
class BOT_STATE(Enum):
    WALKING_BACK = 1
    WANDERING = 2
    GOING_TO_ORE = 3

SYMBOLS = {
    Environment.EMPTY: "  ",
    Environment.WALL:  "██",
}
class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.internal_map = None
        self.current_state = BOT_STATE.WANDERING
        self.original_pos = None
        self.walking_back_first = False
        self.bridge_builder = False
        self.current_target_pos = None
        self.previous_target_pos = None
        self.ore_sites = set()
        self.visited_ores = set()
        self.distance_map = None
        self.target_distance_squared = 0
        self.unexplored = set()
        self.buckets = {}
        self.bucket_size = 16
        
        random.seed(time.time())
        random.shuffle(DIRECTIONS)
        random.shuffle(CARDINAL_DIRECTIONS)

    def run(self, ct: Controller) -> None:
        start_time = ct.get_cpu_time_elapsed()
        if (not self.internal_map):
            self.internal_map = [[None] * ct.get_map_height() for _ in range(ct.get_map_width())]
            for x in range(ct.get_map_width()):
                for y in range(ct.get_map_height()):
                    pos = Position(x, y)
                    self.unexplored.add(pos)
                    bucket = (x // self.bucket_size, y // self.bucket_size)
                    self.buckets.setdefault(bucket, set()).add(pos)

        if (not self.original_pos):
            self.original_pos = ct.get_position()
            self.enemy_pos = Position (ct.get_map_width() - self.original_pos.x, ct.get_map_height() - self.original_pos.y)
            # Bridge builder script, can be ignored
            for id in ct.get_nearby_buildings():
                if ct.get_entity_type(id) == EntityType.CORE and ct.get_team(id) == ct.get_team() and ct.get_position(id) != ct.get_position():
                    self.bridge_builder = True
                    self.original_pos = self.original_pos.add(Direction.NORTH)
                    
        
        if (self.current_target_pos):
            ct.draw_indicator_line(ct.get_position(), self.current_target_pos, 0, 0, 1)

        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if self.num_spawned == 0:
                spawn_pos = ct.get_position().add(Direction.SOUTH)
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
                return
            if self.num_spawned * 500 <= ct.get_global_resources()[0] and self.num_spawned < 2:
                # if we haven't spawned 3 builder bots yet, try to spawn one on a random tile
                spawn_pos = ct.get_position()
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
        elif etype == EntityType.BUILDER_BOT:
            pos = ct.get_position()
            # Updating the map
            for tile in ct.get_nearby_tiles():
                env = ct.get_tile_env(tile)
                building_id = ct.get_tile_building_id(tile)
                if env == Environment.EMPTY and (building_id != None and ((ct.get_entity_type(building_id) not in PASSABLE) or (ct.get_team(building_id) != ct.get_team()))):
                    env = Environment.WALL
                self.internal_map[tile.x][tile.y] = env 
                if tile in self.unexplored:
                    self.unexplored.remove(tile)
                    bucket = (tile.x // self.bucket_size, tile.y // self.bucket_size)
                    self.buckets[bucket].remove(tile)
                    if not self.buckets[bucket]:
                        del self.buckets[bucket]  # prune empty buckets
                if env == Environment.ORE_TITANIUM:
                    self.ore_sites.add(tile)
                    if ct.get_tile_building_id(tile) != None:
                        self.visited_ores.add(tile)
                        
            if (self.bridge_builder):
                build_bridges(ct, self.original_pos)
                return

            # Check if we have reached an ore site
            for d in CARDINAL_DIRECTIONS:
                check_pos = pos.add(d)
                if not is_in_bound(check_pos, ct):
                    continue
                check_id = ct.get_tile_building_id(check_pos)
                if (ct.can_build_harvester(check_pos) and ct.get_tile_env(check_pos) == Environment.ORE_TITANIUM) or (check_id and ct.get_entity_type(check_id) == EntityType.HARVESTER and ct.get_team(check_id) != ct.get_team()):
                    if (ct.can_build_harvester(check_pos)):
                        ct.build_harvester(check_pos)
                    self.current_state = BOT_STATE.WALKING_BACK
                    self.walking_back_first = True
                    self.current_target_pos = self.original_pos
                    self.target_distance_squared = 20
                    return
                
            if (self.current_state == BOT_STATE.WALKING_BACK):
                if pos.distance_squared(self.original_pos) <= 36:
                    buildings_nearby = ct.get_nearby_buildings(9)
                    bridges_nearby = list(filter(lambda b: ct.get_entity_type(b) == EntityType.BRIDGE and ct.get_position(b).distance_squared(self.original_pos) <= 9, buildings_nearby))
                    # We are close enough to the base
                    if len(bridges_nearby) >= 2:
                        bridge_id = random.choice(bridges_nearby)
                        if ct.get_global_resources()[0] >= ct.get_bridge_cost()[0]:
                            if ct.can_destroy(pos):
                                self.current_state = BOT_STATE.WANDERING
                                self.walking_back_first = False
                                self.current_target_pos = None
                                self.previous_target_pos = None
                                self.target_distance_squared = 0
                                ct.destroy(pos)
                                ct.build_bridge(pos, ct.get_position(bridge_id))
                                self._random_movement(ct)   
                        return   

            if (self.current_state == BOT_STATE.WANDERING):
                unvisited = self.ore_sites - self.visited_ores
                if unvisited:
                    self.current_target_pos = min(unvisited, key=lambda p: ct.get_position().distance_squared(p))
                    self.target_distance_squared = 0
                    self.current_state = BOT_STATE.GOING_TO_ORE
        
            print(f"Time before movement {ct.get_cpu_time_elapsed() - start_time}")
            # Move randomly
            if (not self.current_target_pos):
                self._random_movement(ct)

            print(ct.get_cpu_time_elapsed() - start_time)
            if (self.current_target_pos):
                self.move_to_pos(ct)
                
            print(ct.get_cpu_time_elapsed() - start_time)

    def _random_movement(self, ct: Controller):
        if self.current_target_pos:
            if (self.internal_map[self.current_target_pos.x][self.current_target_pos.y] != None):
                self.current_target_pos = self._nearest_unexplored(ct.get_position())
        else:
            self.current_target_pos = self._nearest_unexplored(ct.get_position())
            print(f"Time to select: {ct.get_cpu_time_elapsed()}")
            if not self.current_target_pos:
                # Explored all areas
                self.current_target_pos = self.enemy_pos
    
    
    def _pick_random(self, ct: Controller):
        move_dir = random.choice(DIRECTIONS)
        move_pos = ct.get_position().add(move_dir)
        if ct.can_build_road(move_pos):
            ct.build_road(move_pos)
        if ct.can_move(move_dir):
            ct.move(move_dir)
    
    def _nearest_unexplored(self, pos: Position):
        bx, by = pos.x // self.bucket_size, pos.y // self.bucket_size
        
        # Spiral outward through buckets until we find candidates
        radius = 0
        while True:
            if not self.buckets:
                return None
            candidates = []
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue  # only check the ring
                    bucket = self.buckets.get((bx + dx, by + dy))
                    if bucket:
                        candidates.extend(bucket)
            
            if candidates:
                return min_with_random_tiebreak(candidates, key=lambda c: pos.distance_squared(c))
            
            radius += 1

    def move_to_pos(self, ct: Controller):
        if not self.current_target_pos:
            return
        start_time = ct.get_cpu_time_elapsed()
        pos = ct.get_position()
        if self.current_target_pos:
            if self.current_state == BOT_STATE.WALKING_BACK and pos.distance_squared(self.current_target_pos) <= self.target_distance_squared:
                self.current_state = BOT_STATE.WANDERING
                # We have reached the target
                self.current_target_pos = None
                self.previous_target_pos = None
                self.target_distance_squared = 0
                return
            elif self.current_state == BOT_STATE.WANDERING and pos.distance_squared(self.current_target_pos) <= ct.get_vision_radius_sq():
                self.current_target_pos = None
                self.previous_target_pos = None
                self.target_distance_squared = 0
                return
            elif pos.distance_squared(self.current_target_pos) <= 1:
                self.current_state = BOT_STATE.WANDERING
                self.current_target_pos = None
                self.previous_target_pos = None
                self.target_distance_squared = 0
                return

        if self.previous_target_pos != self.current_target_pos:
            self.previous_target_pos = self.current_target_pos
            print("Start filling!")
            self.distance_map = flood_fill(self.internal_map, self.current_target_pos, pos, self.target_distance_squared)
            print(f"Fill time: {ct.get_cpu_time_elapsed() - start_time}")
        
        decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(d), ct)]
        chosen = min(decisions, key=lambda d: get_from_dir(self.distance_map, pos, d))
        move_pos = pos.add(chosen)

        if not self.distance_map[move_pos.x][move_pos.y] or math.isinf(self.distance_map[move_pos.x][move_pos.y]):
            self.print_distance_map()
            raise RuntimeError

        # Make sure to place a conveyer at standing point on the first iteration
        if (self.walking_back_first):
            if (ct.get_global_resources()[0] >= ct.get_conveyor_cost()[0]):
                if ct.can_destroy(pos):
                    ct.destroy(pos)
                    ct.build_conveyor(pos, chosen)
                    self.walking_back_first = False
            return
        
        if (self.current_state == BOT_STATE.WALKING_BACK):
            next_decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(chosen).add(d), ct)]
            next_chosen = min(next_decisions, key=lambda d: get_from_dir(self.distance_map, pos.add(chosen), d))

            if (ct.can_build_conveyor(move_pos, next_chosen)):
                ct.build_conveyor(move_pos, next_chosen)
            elif ct.can_destroy(move_pos):
                tile_id = ct.get_tile_building_id(move_pos)
                if not (
                    ct.get_entity_type(tile_id) == EntityType.CONVEYOR and 
                    (
                        get_from_dir(self.distance_map, pos.add(chosen), ct.get_direction(ct.get_tile_building_id(move_pos)))
                        == get_from_dir(self.distance_map, pos.add(chosen), next_chosen)
                    )
                ):
                    ct.destroy(move_pos)
                    if ct.can_build_conveyor(move_pos, next_chosen):
                        ct.build_conveyor(move_pos, next_chosen)
                else:
                    self.current_target_pos = None
                    self.previous_target_pos = None
                    self.target_distance_squared = 0
                    self.current_state = BOT_STATE.WANDERING
                    self.walking_back_first = False
            if ct.can_move(chosen):
                ct.move(chosen)
            else:
                print("Oh no i hit a wall")
                self.walking_back_first = True
                self.distance_map = flood_fill(self.internal_map, self.current_target_pos, pos)
            return
        if ct.can_build_road(move_pos):
            ct.build_road(move_pos)
        if ct.can_move(chosen):
            ct.move(chosen)
        elif ct.get_tile_env(move_pos) == Environment.EMPTY:
            # We have blocked another bot
            self._pick_random(ct)
        else:
            # Maybe we have hit a wall, so update the distance_map
            self.distance_map = flood_fill(self.internal_map, self.current_target_pos, pos, self.target_distance_squared)
        print(f"Total time: {ct.get_cpu_time_elapsed() - start_time}")

    def print_distance_map(self):
        def map_to_string(c):
            if c is None:
                return "__"
            if math.isinf(c):
                return "██"
            return f"{c:02d}"

        for row in zip(*self.distance_map):
            print("".join(map_to_string(cell) for cell in row))

    def print_map(self):
        for row in zip(*self.internal_map):
            print("".join("██" if cell == Environment.WALL else "  " for cell in row))

def is_in_bound(pos: Position, ct: Controller):
    return pos.x in range(ct.get_map_width()) and pos.y in range(ct.get_map_height())

def get_from_dir(map: list[list], pos: Position, dir: Direction):
    p1 = pos.add(dir)
    val = map[p1.x][p1.y]
    return val if val != None else math.inf

def build_bridges(ct: Controller, foundary_pos: Position):
    move_dir = random.choice(DIRECTIONS)
    move_pos = ct.get_position().add(move_dir)
    if ct.can_move(move_dir) and move_pos.distance_squared(foundary_pos) <= 9:
        ct.move(move_dir)
    
    for d in DIRECTIONS:
        bridge_pos = ct.get_position().add(d)
        if ct.can_build_bridge(bridge_pos, foundary_pos):
            ct.build_bridge(bridge_pos, foundary_pos)
            return
        
        if not is_in_bound(bridge_pos, ct):
            return
        
        tile_id = ct.get_tile_building_id(bridge_pos)
        if tile_id and ct.get_entity_type(tile_id) != EntityType.BRIDGE and ct.get_position(tile_id).distance_squared(foundary_pos) <= 9:
            if ct.can_destroy(bridge_pos):
                ct.destroy(bridge_pos)
            if ct.can_build_bridge(bridge_pos, foundary_pos):
                ct.build_bridge(bridge_pos, foundary_pos)
                return

def min_with_random_tiebreak(iterable, key=None):
    it = iter(iterable)
    try:
        first = next(it)
    except StopIteration:
        return None

    keyed = key or (lambda x: x)
    candidates = [first]
    min_key = keyed(first)

    for x in it:
        k = keyed(x)
        if k < min_key:
            min_key = k
            candidates = [x]
        elif k == min_key:
            candidates.append(x)

    return random.choice(candidates)