import random
import math
from enum import Enum
from cambc import Controller, Direction, EntityType, Environment, Position
from path_finder_two import flood_fill, get_cardinal
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
        if (not self.original_pos):
            core_center = find_core_center(ct)
            if core_center:
                self.original_pos = core_center
            else:
                self.original_pos = ct.get_position()
            self.enemy_pos = Position (ct.get_map_width() - self.original_pos.x, ct.get_map_height() - self.original_pos.y)
            d = clamp(self.original_pos, ct.get_position())
            self.current_target_pos = ct.get_position().add(d).add(d)
            self.current_state = BOT_STATE.GOING_TO_ORE
        
        if (self.current_target_pos):
            ct.draw_indicator_line(ct.get_position(), self.current_target_pos, 0, 0, 1)

        print(f"Bot is currently {self.current_state}")

        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if self.num_spawned * 250 <= ct.get_global_resources()[0] and self.num_spawned < 20:
                # if we haven't spawned 3 builder bots yet, try to spawn one on a random tile
                spawn_pos = ct.get_position().add(random.choice(CARDINAL_DIRECTIONS))
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
        elif etype == EntityType.BUILDER_BOT:
            if (not self.internal_map):
                self.internal_map = [[None] * ct.get_map_height() for _ in range(ct.get_map_width())]
                for x in range(ct.get_map_width()):
                    for y in range(ct.get_map_height()):
                        pos = Position(x, y)
                        self.unexplored.add(pos)
                        bucket = (x // self.bucket_size, y // self.bucket_size)
                        self.buckets.setdefault(bucket, set()).add(pos)

            pos = ct.get_position()
            # Updating the map
            for tile in ct.get_nearby_tiles():
                env = ct.get_tile_env(tile)
                building_id = ct.get_tile_building_id(tile)
                if env == Environment.EMPTY and (
                        building_id != None and 
                        (
                            (ct.get_entity_type(building_id) not in PASSABLE) or 
                            (ct.get_team(building_id) != ct.get_team())
                        )
                    ):
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
                    temp_id = ct.get_tile_building_id(tile)
                    if temp_id and ct.get_team(temp_id) == ct.get_team():
                        self.visited_ores.add(tile)

            # Check if we have reached an ore site
            if self.current_state != BOT_STATE.WALKING_BACK:
                for d in CARDINAL_DIRECTIONS:
                    check_pos = pos.add(d)
                    if not is_in_bound(check_pos, ct):
                        continue
                    check_id = ct.get_tile_building_id(check_pos)
                    if (ct.can_build_harvester(check_pos) and ct.get_tile_env(check_pos) == Environment.ORE_TITANIUM) or (check_id and ct.get_entity_type(check_id) == EntityType.HARVESTER and ct.get_team(check_id) != ct.get_team()):
                        if (ct.can_build_harvester(check_pos)):
                            ct.build_harvester(check_pos)
                        self.visited_ores.add(check_pos)
                        self.current_state = BOT_STATE.WALKING_BACK
                        self.walking_back_first = True
                        self.current_target_pos = self.original_pos
                        self.target_distance_squared = 16
                        return
                
            if (self.current_state == BOT_STATE.WALKING_BACK):
                if pos.distance_squared(self.original_pos) <= 49:
                    buildings_nearby = ct.get_nearby_buildings(9)
                    bridges_nearby = list(filter(lambda b: ct.get_entity_type(b) == EntityType.BRIDGE and ct.get_position(b).distance_squared(self.original_pos) <= 16 and ct.get_team(b) == ct.get_team(), buildings_nearby))
                    # We are close enough to the base
                    if len(bridges_nearby) >= 1:
                        bridge_id = random.choice(bridges_nearby)
                        if ct.get_global_resources()[0] >= ct.get_bridge_cost()[0]:
                            if ct.can_destroy(pos):
                                temp_id = ct.get_tile_building_id(pos)
                                self.current_state = BOT_STATE.WANDERING
                                self.walking_back_first = False
                                self.current_target_pos = None
                                self.previous_target_pos = None
                                self.target_distance_squared = 0
                                if temp_id and ct.get_team(temp_id) == ct.get_team() and ct.get_entity_type(temp_id) == EntityType.BRIDGE:
                                    pass
                                else:
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
        
            # Move randomly
            if (not self.current_target_pos):
                self._random_movement(ct)

            if (self.current_target_pos):
                self.move_to_pos(ct)

    def _random_movement(self, ct: Controller):
        if self.current_target_pos:
            if (self.internal_map[self.current_target_pos.x][self.current_target_pos.y] != None):
                self.current_target_pos = self._nearest_unexplored(ct.get_position())
        else:
            self.current_target_pos = self._nearest_unexplored(ct.get_position())
            if not self.current_target_pos:
                # Explored all areas
                self.current_target_pos = self.enemy_pos
    
    
    def _pick_random(self, ct: Controller):
        move_dir = random.choice(DIRECTIONS)
        move_pos = ct.get_position().add(move_dir)
        self.build_road(ct, move_pos)
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
        print(f"Start time: {start_time}")

        if self.current_state == BOT_STATE.WALKING_BACK and pos.distance_squared(self.current_target_pos) <= self.target_distance_squared:
            self.current_state = BOT_STATE.WANDERING
            self.current_target_pos = None
            self.previous_target_pos = None
            self.target_distance_squared = 0
            self.distance_map = None
            return
        elif self.current_state == BOT_STATE.WANDERING and pos.distance_squared(self.current_target_pos) <= ct.get_vision_radius_sq():
            self.current_target_pos = None
            self.previous_target_pos = None
            self.target_distance_squared = 0
            self.distance_map = None
            return
        elif pos.distance_squared(self.current_target_pos) <= 1:
            self.current_state = BOT_STATE.WANDERING
            self.current_target_pos = None
            self.previous_target_pos = None
            self.target_distance_squared = 0
            self.distance_map = None
            return

        print(self.previous_target_pos == self.current_target_pos)
        if self.previous_target_pos != self.current_target_pos or not self.distance_map:
            self.previous_target_pos = self.current_target_pos
            print("Start filling!")
            self.distance_map = flood_fill(self.internal_map, self.current_target_pos, pos, self.target_distance_squared)
            print(f"Fill time: {ct.get_cpu_time_elapsed() - start_time}")
        
        decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(d), ct)]
        chosen = min(decisions, key=lambda d: get_from_dir(self.distance_map, pos, d))
        if math.isinf(get_from_dir(self.distance_map, pos, chosen)):
            # This shouldn't happen at all, but as a fail safe:
            print("Please fix")
            self.internal_map = None
            self.previous_target_pos = None
            self.print_distance_map()
            return
        move_pos = pos.add(chosen)

        if self.walking_back_first:
            print("a")
            if ct.get_global_resources()[0] >= ct.get_conveyor_cost()[0]:
                print("b")
                if ct.can_destroy(pos):
                    print("c")
                    building_id = ct.get_tile_building_id(pos)
                    if building_id and ct.get_entity_type(building_id) == EntityType.BRIDGE and ct.get_team(building_id) == ct.get_team():
                        self.walking_back_first = False
                        return
                    ct.destroy(pos)
                    ct.build_conveyor(pos, chosen)
                    self.walking_back_first = False
            return
        
        if self.current_state == BOT_STATE.WALKING_BACK:
            if self.check_for_bot(move_pos, ct):
                # Wait
                return

            next_decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(chosen).add(d), ct)]
            next_chosen = min(next_decisions, key=lambda d: get_from_dir(self.distance_map, pos.add(chosen), d))

            if ct.can_build_conveyor(move_pos, next_chosen) and ct.get_tile_env(move_pos) not in [Environment.ORE_AXIONITE, Environment.ORE_TITANIUM]:
                ct.build_conveyor(move_pos, next_chosen)
            elif ct.can_destroy(move_pos):
                tile_id = ct.get_tile_building_id(move_pos)
                if ( 
                    ct.get_entity_type(tile_id) == EntityType.CONVEYOR and 
                    get_from_dir(self.distance_map, pos.add(chosen), ct.get_direction(tile_id))
                    == get_from_dir(self.distance_map, pos.add(chosen), next_chosen)
                ) or (
                    ct.get_team(tile_id) == ct.get_team() and
                    ct.get_entity_type(tile_id) == EntityType.BRIDGE
                ):
                    self.current_target_pos = None
                    self.previous_target_pos = None
                    self.target_distance_squared = 0
                    self.current_state = BOT_STATE.WANDERING
                    self.walking_back_first = False
                    self.distance_map = None
                else:
                    ct.destroy(move_pos)
                    if ct.can_build_conveyor(move_pos, next_chosen):
                        ct.build_conveyor(move_pos, next_chosen)

            if ct.can_move(chosen):
                ct.move(chosen)
            else:
                print("Oh no i hit a wall")
                self.walking_back_first = True
                self.distance_map = None  # force repath, don't abandon target
            return

        self.build_road(ct, move_pos)
        if ct.can_move(chosen):
            ct.move(chosen)
        elif ct.get_tile_env(move_pos) == Environment.EMPTY:
            if self.current_state != BOT_STATE.WALKING_BACK and self.check_for_bot(move_pos, ct):
                self._pick_random(ct)
        else:
            self.distance_map = None  # hit a real wall, repath
        print(f"Total time: {ct.get_cpu_time_elapsed() - start_time}")
    
    def build_road(self, ct: Controller, move_pos: Position):
        print(f"Trying to build road at: {move_pos}")
        direction = clamp(move_pos, self.original_pos)
        target_pos = move_pos.add(direction).add(direction).add(direction)
    
        building_id = ct.get_tile_building_id(target_pos) if is_in_bound(target_pos, ct) else None
        if (building_id and ct.get_entity_type(building_id) == EntityType.CORE and ct.get_team(building_id) == ct.get_team()):
            if (ct.can_build_bridge(move_pos, target_pos)):
                ct.build_bridge(move_pos, target_pos)
            return
        
        if (ct.can_build_road(move_pos) and ct.get_tile_env(move_pos) not in [Environment.ORE_AXIONITE, Environment.ORE_TITANIUM]):
            ct.build_road(move_pos)
        
    def check_for_bot(self, target_pos: Position, ct: Controller):
        for ent_id in ct.get_nearby_entities():
            if ct.get_entity_type(ent_id) == EntityType.BUILDER_BOT and ct.get_position(ent_id) == target_pos:
                # Another bot is blocking 
                return True
            
        return False

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

def clamp(pos1: Position, pos2: Position) -> Direction:
    dx = pos2.x - pos1.x
    dy = pos2.y - pos1.y

    if abs(dx) >= abs(dy):
        return Direction.EAST if dx > 0 else Direction.WEST
    else:
        return Direction.SOUTH if dy > 0 else Direction.NORTH
    
def direction_to_delta(direction: Direction) -> Position:
    return {
        Direction.NORTH: Position(0, -1),
        Direction.SOUTH: Position(0,  1),
        Direction.EAST:  Position(1,  0),
        Direction.WEST:  Position(-1, 0),
    }[direction]

def find_core_center(ct: Controller) -> Position | None:
    core_tiles = set()
    for tile in ct.get_nearby_tiles():
        tile_id = ct.get_tile_building_id(tile)
        if tile_id and ct.get_entity_type(tile_id) == EntityType.CORE and ct.get_team(tile_id) == ct.get_team():
            core_tiles.add((tile.x, tile.y))
    
    # For each core tile, check if it is the center of a 3x3 block of cores
    for (cx, cy) in core_tiles:
        if all((cx + dx, cy + dy) in core_tiles
               for dx in range(-1, 2)
               for dy in range(-1, 2)):
            return Position(cx, cy)
    
    return None
