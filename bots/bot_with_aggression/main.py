from enum import Enum
from player_utils import *

from path_finder_two import flood_fill

class BOT_STATE(Enum):
    WALKING_BACK = 1
    WANDERING = 2
    GOING_TO_ORE = 3
    BOMBER = 4

class BOT_TYPE(Enum):
    NORMAL = 1
    AGGRESSOR = 2
    INITIATORS = 3

SYMBOLS = {
    Environment.EMPTY: "  ",
    Environment.WALL:  "██",
}


class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.bomber_spawned = 0 # number of aggressers spawned so far (core)
        self.spawn_queue = [Direction.NORTHEAST, Direction.SOUTHWEST, Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]

        self.internal_map = None
        self.internal_walkable_map = None
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
        self.bot_type = BOT_TYPE.NORMAL

        self.enemy_pos = None
        self.home_pos = None

    def run(self, ct: Controller) -> None:
        map_height = ct.get_map_height()
        map_width = ct.get_map_width()
        position = ct.get_position()
        current_round = ct.get_current_round()
        global_resources = ct.get_global_resources()[0]
        builder_bot_cost = ct.get_builder_bot_cost()[0]
        sentinel_cost = ct.get_sentinel_cost()[0]
        bridge_cost = ct.get_bridge_cost()[0]
        action_cooldown = ct.get_action_cooldown()

        if not self.original_pos:
            core_center = find_core_center(ct)
            self.original_pos = core_center or position
            
            if abs(self.original_pos.x - position.x) + abs(self.original_pos.y - position.y) == 2:
                self.bot_type = BOT_TYPE.AGGRESSOR
            
            self.enemy_pos = Position(map_width - self.original_pos.x, map_height - self.original_pos.y)
            if self.bot_type == BOT_TYPE.NORMAL:
                d = clamp(self.original_pos, position)
                self.home_pos = position.add(d)
                self.current_target_pos = position.add(d).add(d).add(d)
                self.current_state = BOT_STATE.GOING_TO_ORE
            # elif self.bot_type == BOT_TYPE.AGGRESSOR:
            #     pass
        
        if self.current_target_pos:
            ct.draw_indicator_line(position, self.current_target_pos, 0, 0, 1)

        # print(f"Bot is currently {self.current_state}")

        etype = ct.get_entity_type()
        match etype:
            case EntityType.CORE:
                if self.spawn_queue:
                    # print(self.spawn_queue)
                    direction = self.spawn_queue.pop(0) if self.spawn_queue else random.choice(CARDINAL_DIRECTIONS)
                    spawn_pos = position.add(direction)
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1
                        # print(f"Spawned: {self.num_spawned}")
                        return
                if ((not self.spawn_queue or current_round >= 100) and
                        global_resources >= builder_bot_cost + sentinel_cost + 10 and self.num_spawned <= 500):
                    # print("Boom!")
                    direction = random.choice(DIAGONAL_DIRECTIONS)
                    spawn_pos = ct.get_position().add(direction)
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1
                        return
            case EntityType.SENTINEL:
                for d in DIAGONAL_DIRECTIONS:
                    if not ct.get_tile_building_id(position.add(d)):
                        ct.place_marker(position.add(d), 2)
                        break
                for entity_id in ct.get_nearby_entities():
                    try:
                        if ct.get_team(entity_id) != ct.get_team():
                            if ct.can_fire(ct.get_position(entity_id)):
                                ct.fire(ct.get_position(entity_id))
                    except Exception:
                        continue

            case EntityType.BUILDER_BOT:
                if not self.internal_map:
                    self.internal_map = [[None] * map_height for _ in range(map_width)]
                    self.internal_walkable_map = [[None] * map_height for _ in range(map_width)]
                    for x in range(map_width):
                        for y in range(map_height):
                            pos = Position(x, y)
                            self.unexplored.add(pos)
                            bucket = (x // self.bucket_size, y // self.bucket_size)
                            self.buckets.setdefault(bucket, set()).add(pos)

                # Updating the map
                self.update_map(ct)

                if self.bot_type == BOT_TYPE.INITIATORS:
                    self.initiator_script(ct)

                if self.bot_type == BOT_TYPE.AGGRESSOR:
                    self.aggressor_script(ct)
                    return

                # Check if we have reached an ore site
                if self.current_state != BOT_STATE.WALKING_BACK:
                    for d in CARDINAL_DIRECTIONS:
                        check_pos = position.add(d)
                        if not is_in_bound(check_pos, ct):
                            continue
                        check_id = ct.get_tile_building_id(check_pos)
                        # print(f"Waiting for money... {harvester_cost}/{global_resources}")
                        # print(ct.get_action_cooldown())

                        can_build_h = ct.can_build_harvester(check_pos)
                        if can_build_h or (check_id and ct.get_entity_type(check_id) == EntityType.HARVESTER
                                           and ct.get_team(check_id) != ct.get_team()):
                            if can_build_h:
                                ct.build_harvester(check_pos)
                            self.visited_ores.add(check_pos)
                            self.current_state = BOT_STATE.WALKING_BACK
                            self.walking_back_first = True
                            self.current_target_pos = self.home_pos
                            self.target_distance_squared = 4
                            return

                # Check if we reach close enough to the base
                if self.current_state == BOT_STATE.WALKING_BACK:
                    if position.distance_squared(self.original_pos) <= 49:
                        buildings_nearby = ct.get_nearby_buildings(9)
                        bridges_nearby = [
                            b for b in buildings_nearby if
                            ct.get_entity_type(b) == EntityType.SPLITTER and
                            ct.get_position(b).distance_squared(self.original_pos) <= 16 and
                            ct.get_team(b) == ct.get_team()
                        ]

                        # We are close enough to the base
                        if len(bridges_nearby) >= 1:
                            bridge_id = random.choice(bridges_nearby)
                            if global_resources >= bridge_cost and action_cooldown == 0:
                                if ct.can_destroy(position):
                                    temp_id = ct.get_tile_building_id(position)
                                    self.current_state = BOT_STATE.WANDERING
                                    self.walking_back_first = False
                                    self.current_target_pos = None
                                    self.previous_target_pos = None
                                    self.target_distance_squared = 0

                                    same_team = temp_id and ct.get_team(temp_id) == ct.get_team()
                                    is_bridge = same_team and ct.get_entity_type(temp_id) == EntityType.BRIDGE
                                    if not is_bridge:
                                        ct.destroy(position)
                                        ct.build_bridge(position, ct.get_position(bridge_id))
                                    self._random_movement(ct)
                            return

                # Go to an ore site
                if self.current_state == BOT_STATE.WANDERING:
                    unvisited = self.ore_sites - self.visited_ores
                    if unvisited:
                        self.current_target_pos = min(unvisited, key=lambda p: position.distance_squared(p))
                        self.target_distance_squared = 0
                        self.current_state = BOT_STATE.GOING_TO_ORE

                # Move randomly
                if not self.current_target_pos:
                    self._random_movement(ct)

                if self.current_target_pos:
                    self.move_to_pos(ct)

                if ct.can_heal(self.original_pos):
                    ct.heal(self.original_pos)

    def _random_movement(self, ct: Controller):
        pos = ct.get_position() if self.bot_type != BOT_TYPE.AGGRESSOR else self.enemy_pos
        if self.current_target_pos:
            if (self.internal_map[self.current_target_pos.x][self.current_target_pos.y] != None):
                self.current_target_pos = self._nearest_unexplored(pos)
        else:
            self.current_target_pos = self._nearest_unexplored(pos)
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
    
    def update_map(self, ct: Controller):
        for tile in ct.get_nearby_tiles():
            env = ct.get_tile_env(tile)
            envp = env
            building_id = ct.get_tile_building_id(tile)
            if env == Environment.EMPTY and building_id != None:
                if (ct.get_entity_type(building_id) == EntityType.MARKER and ct.get_team(building_id) == ct.get_team()):
                    print(tile)
                    print(ct.get_action_cooldown())
                    if ct.get_marker_value(building_id) == 1 and ct.can_build_sentinel(tile, clamp(self.original_pos, tile)):
                        if (self.bot_type != BOT_TYPE.INITIATORS and ct.get_current_round() >= 50):
                            ct.build_sentinel(tile, clamp(self.original_pos, tile))
                        splitter_id = ct.get_tile_building_id(ct.get_position())
                        if (ct.get_entity_type(splitter_id) == EntityType.SPLITTER):
                            direction = ct.get_direction(splitter_id)
                            pos = ct.get_position(splitter_id)
                            left_cardinal = direction.rotate_left().rotate_left()
                            right_cardinal = direction.rotate_right().rotate_right()
                            
                            if not ct.get_tile_building_id(pos.add(left_cardinal)) and ct.can_place_marker(pos.add(left_cardinal)):
                                ct.place_marker(pos.add(left_cardinal), 1)
                            elif not ct.get_tile_building_id(pos.add(left_cardinal)) and ct.can_place_marker(pos.add(right_cardinal)):
                                ct.place_marker(pos.add(right_cardinal), 1)
                            elif not ct.get_tile_building_id(pos.add(left_cardinal)) and ct.can_place_marker(pos.add(direction.opposite())):
                                ct.place_marker(pos.add(direction.opposite()), 2)
                    elif ct.get_marker_value(building_id) == 2 and ct.can_build_barrier(tile):
                        ct.build_barrier(tile)
                    env = Environment.WALL
                    envp = env
                else:
                    if (ct.get_entity_type(building_id) not in PASSABLE):
                        env = Environment.WALL
                        envp = env
                    elif (ct.get_entity_type(building_id) == EntityType.MARKER and ct.get_team(building_id) == ct.get_team(building_id)):
                        env = Environment.WALL
                        envp = env
                    if (ct.get_team(building_id) != ct.get_team()):
                        env = Environment.WALL
                        if ct.get_entity_type(building_id) == EntityType.CORE:
                            envp = Environment.WALL
            self.internal_map[tile.x][tile.y] = env 
            self.internal_walkable_map[tile.x][tile.y] = envp
            if tile in self.unexplored:
                self.unexplored.remove(tile)
                bucket = (tile.x // self.bucket_size, tile.y // self.bucket_size)
                self.buckets[bucket].remove(tile)
                if not self.buckets[bucket]:
                    del self.buckets[bucket]  # prune empty buckets
            if env in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                self.ore_sites.add(tile)
                temp_id = ct.get_tile_building_id(tile)
                if temp_id and ct.get_team(temp_id) == ct.get_team():
                    self.visited_ores.add(tile)

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
            if self.buckets:
                self._random_movement(ct)
                self.move_to_pos(ct)
            return
        elif abs(pos.x - self.current_target_pos.x) + abs(pos.y - self.current_target_pos.y) <= 1:
            self.current_state = BOT_STATE.WANDERING
            self.current_target_pos = None
            self.previous_target_pos = None
            self.target_distance_squared = 0
            self.distance_map = None
            return

        if self.previous_target_pos != self.current_target_pos or not self.distance_map:
            self.previous_target_pos = self.current_target_pos
            print("Start filling!")
            self.distance_map = flood_fill((self.internal_map if self.current_state == BOT_STATE.WALKING_BACK else self.internal_walkable_map), self.current_target_pos, pos, self.target_distance_squared, self.current_state != BOT_STATE.WALKING_BACK)
            self.print_distance_map()
            print(f"Fill time: {ct.get_cpu_time_elapsed() - start_time}")
        
        print(pos.distance_squared(self.current_target_pos))
        decisions = [d for d in (CARDINAL_DIRECTIONS if self.current_state == BOT_STATE.WALKING_BACK or max(abs(pos.x - self.current_target_pos.x), abs(pos.y - self.current_target_pos.y)) == 1 else DIRECTIONS) if is_in_bound(pos.add(d), ct)]
        chosen = min(decisions, key=lambda d: get_from_dir(self.distance_map, pos, d))
        print(f"Chosen direction: {chosen}")

        if math.isinf(get_from_dir(self.distance_map, pos, chosen)):
            # This shouldn't happen at all, but as a fail safe:
            print("Please fix")
            self.internal_map = None
            self.previous_target_pos = None
            self.current_target_pos = None
            self._random_movement(ct)
            return
        move_pos = pos.add(chosen)

        if self.walking_back_first:
            if ct.get_global_resources()[0] >= ct.get_conveyor_cost()[0]:
                if ct.can_destroy(pos):
                    building_id = ct.get_tile_building_id(pos)
                    if building_id and ct.get_entity_type(building_id) == EntityType.BRIDGE and ct.get_team(building_id) == ct.get_team():
                        self.walking_back_first = False
                        return
                    ct.destroy(pos)
                    ct.build_conveyor(pos, chosen)
                    self.walking_back_first = False
            return
        
        if self.current_state == BOT_STATE.WALKING_BACK:
            if check_for_bot(move_pos, ct):
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

            building_id = ct.get_tile_building_id(move_pos)
            if ct.can_move(chosen) and not(building_id and ct.get_team(building_id) != ct.get_team()):
                ct.move(chosen)
            else:
                print("Oh no i hit a wall")
                self.walking_back_first = True
                self.distance_map = None  # force repath, don't abandon target
            return

        self.build_road(ct, move_pos)
        if ct.can_move(chosen):
            ct.move(chosen)
        elif ct.get_tile_env(move_pos) == Environment.EMPTY and self.current_state != BOT_STATE.WALKING_BACK and check_for_bot(move_pos, ct):
            self._pick_random(ct)
        else:
            self.distance_map = None  # hit a real wall, repath
        print(f"Total time: {ct.get_cpu_time_elapsed() - start_time}")
    
    def build_road(self, ct: Controller, move_pos: Position):
        print(f"Trying to build road at: {move_pos}")
        direction = clamp(self.original_pos, move_pos)
        if not is_in_bound(move_pos, ct):
            return
        
        if ct.get_tile_env(move_pos) != Environment.EMPTY:
            return
        
        if move_pos == self.original_pos.add(direction).add(direction):
            if (ct.can_build_splitter(move_pos, direction.opposite()) and ct.get_tile_env(move_pos) not in [Environment.ORE_AXIONITE, Environment.ORE_TITANIUM]):
                ct.build_splitter(move_pos, direction.opposite())
                left_cardinal = direction.rotate_left().rotate_left()
                right_cardinal = direction.rotate_right().rotate_right()

                if ct.can_place_marker(move_pos.add(left_cardinal)):
                    ct.place_marker(move_pos.add(left_cardinal), 1)
                
                if ct.can_place_marker(move_pos.add(right_cardinal)):
                    ct.place_marker(move_pos.add(right_cardinal), 1)
                
                self.bot_type = BOT_TYPE.INITIATORS
        
        if (ct.can_build_road(move_pos) and ct.get_tile_env(move_pos) not in [Environment.ORE_AXIONITE, Environment.ORE_TITANIUM]):
            ct.build_road(move_pos)

    def aggressor_script(self, ct: Controller):
        if self.bot_type != BOT_TYPE.AGGRESSOR:
            # Safety
            return
        
        if not self.current_target_pos:
            self._random_movement(ct)
        
        pos = ct.get_position()
        building_id = ct.get_tile_building_id(pos)
        if building_id and ct.get_team() != ct.get_team(building_id) and ct.get_entity_type(building_id) != EntityType.ROAD and connected_to_enemy_core(pos, building_id, ct):
            ct.self_destruct()
            return

        if self.current_target_pos:
            self.move_to_pos(ct)
        
    def initiator_script(self, ct: Controller):
        return

    def print_distance_map(self):
        def map_to_string(c):
            if c is None:
                return "__"
            if math.isinf(c):
                return "██"
            return f"{math.ceil(c):02d}"

        for row in zip(*self.distance_map):
            print("".join(map_to_string(cell) for cell in row))

    def print_map(self):
        for row in zip(*self.internal_map):
            print("".join("██" if cell == Environment.WALL else "  " for cell in row))