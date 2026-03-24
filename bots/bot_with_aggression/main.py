from enum import Enum
from player_utils import *
from collections import defaultdict
from path_finder_two import flood_fill

class BOT_STATE(Enum):
    WALKING_BACK = 1
    WANDERING = 2
    GOING_TO_TARGET = 3
    BOMBER = 4

class BOT_TYPE(Enum):
    NORMAL = 1
    AGGRESSOR = 2
    INITIATORS = 3
    REPAIR = 4

SYMBOLS = {
    Environment.EMPTY: "  ",
    Environment.WALL:  "██",
}


class Player:
    def __init__(self):
        self.num_spawned = 0
        self.bomber_spawned = 0
        self.spawn_queue = [Direction.NORTH, Direction.NORTHEAST, Direction.NORTHWEST, Direction.CENTRE]

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
        self.target_distance_squared = 1
        self.unexplored = set()
        self.buckets = {}
        self.bucket_size = 16
        self.bot_type = BOT_TYPE.INITIATORS
        self.previous_pos = None
        self.stuck_counter = 0

        self.other_potential_enemy_base_pos = []

        self.dementia_rate = 0.99
        self.be_a_bitch_rate = 0.8

        self.aggressor_has_target = False
        self.enemy_pos = None
        self.home_pos = None

    def run(self, ct: Controller) -> None:
        map_height = ct.get_map_height()
        map_width = ct.get_map_width()
        position = ct.get_position()
        current_round = ct.get_current_round()
        harvester_cost = ct.get_harvester_cost()[0]
        global_resources = ct.get_global_resources()[0]
        if not self.original_pos:
            core_center = ct.get_position(ct.get_tile_building_id(position))
            self.original_pos = core_center or position
            if core_center == position:
                self.bot_type = BOT_TYPE.REPAIR
            
            self.enemy_pos = Position(map_width - self.original_pos.x - 1, map_height - self.original_pos.y - 1)
            self.other_potential_enemy_base_pos = [
                Position(self.original_pos.x, map_height - self.original_pos.y - 1), 
                Position(map_width - self.original_pos.x - 1, self.original_pos.y)
            ]

            if get_skibidi_distance(self.original_pos, position) == 2 and not (current_round >= 20 and random.random() > 0.8):
                self.bot_type = BOT_TYPE.AGGRESSOR
                self.current_state = BOT_STATE.WANDERING
                self.target_distance_squared = 1
                self.current_target_pos = self.enemy_pos
            if self.bot_type == BOT_TYPE.INITIATORS:
                d = clamp(self.original_pos, position)
                self.home_pos = position
                self.current_target_pos = position.add(d).add(d)
                self.current_state = BOT_STATE.GOING_TO_TARGET
                self.target_distance_squared = 1
            # elif self.bot_type == BOT_TYPE.AGGRESSOR:
            #     pass
        
        if self.current_target_pos:
            ct.draw_indicator_line(position, self.current_target_pos, 0, 0, 1)
            print(f"Current target: {self.current_target_pos}")
        
        # Pretty important debug and minimal impact pls don't comment
        print(f"Bot of type {self.bot_type} is currently {self.current_state}")

        etype = ct.get_entity_type()
        match etype:
            case EntityType.CORE:
                if self.spawn_queue:
                    direction = self.spawn_queue[0] if self.spawn_queue else random.choice(CARDINAL_DIRECTIONS)
                    spawn_pos = position.add(direction)
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1
                        self.spawn_queue.pop(0)
                        return
                if (
                    not self.spawn_queue and current_round >= 80 and
                    (
                        ct.get_current_round() >= 400 or # Go ham
                        global_resources >= harvester_cost * 1.5
                    )
                    and self.num_spawned <= 500
                ):
                    direction = random.choice(DIAGONAL_DIRECTIONS)
                    spawn_pos = ct.get_position().add(direction)
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1
                        return
                if current_round == 50:
                    self.spawn_queue.append(Direction.SOUTH)
                    
                if current_round % 50 == 0:
                    self.spawn_queue.append(random.choice(DIAGONAL_DIRECTIONS))
            case EntityType.SENTINEL | EntityType.GUNNER:
                candidate = None
                
                for tile in ct.get_nearby_tiles():
                    if not ct.can_fire(tile):
                        continue
                    building_id = ct.get_tile_building_id(tile)
                    bot_id = ct.get_tile_builder_bot_id(tile)
                    entity_id = bot_id or building_id
                    if entity_id:
                        print(ct.get_entity_type(entity_id))
                    try:
                        if entity_id and ct.get_team(entity_id) != ct.get_team():
                            etype = ct.get_entity_type(entity_id)
                            value = VALUABLE_ENEMY_ENTITIES.index(etype) + 5 if etype in VALUABLE_ENEMY_ENTITIES else 3
                            if building_id and bot_id and ct.get_entity_type(building_id) == EntityType.CORE:
                                value = 1000
                            if (candidate is None or value > candidate[1]) and etype != EntityType.HARVESTER:
                                candidate = (entity_id, value, tile)
                    except Exception:
                        continue
                
                if candidate and ct.can_fire(candidate[2]):
                    ct.fire(candidate[2])
            case EntityType.BREACH:
                for tile in ct.get_nearby_tiles():
                    if ct.can_fire(tile):
                        ct.fire(tile)
                        return

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
                match self.bot_type:
                    case BOT_TYPE.INITIATORS:
                        if self.initiator_script(ct):
                            return
                    case BOT_TYPE.AGGRESSOR:
                        if self.aggressor_script(ct):
                            return
                    case BOT_TYPE.NORMAL:
                        if self.initiator_script(ct):
                            return
                    case BOT_TYPE.REPAIR:
                        if self.repair_script(ct):
                            return
                # Move randomly
                if not self.current_target_pos and self.bot_type == BOT_TYPE.INITIATORS:
                    # print("Picking random place!")
                    self._random_movement(ct)

                if self.current_target_pos:
                    self.move_to_pos(ct)

                for d in DIRECTIONS + [Direction.CENTRE]:
                    heal_pos = position.add(d)
                    if ct.can_heal(heal_pos):
                        ct.heal(heal_pos)
                        return

    def _random_movement(self, ct: Controller):
        if self.bot_type == BOT_TYPE.AGGRESSOR:
            return
        pos = ct.get_position()
        if self.current_target_pos:
            if self.internal_map[self.current_target_pos.x][self.current_target_pos.y] is not None:
                self.current_target_pos = self._nearest_unexplored(pos)
        else:
            self.current_target_pos = self._nearest_unexplored(pos)
            if not self.current_target_pos:
                # Explored all areas
                self.current_target_pos = self.enemy_pos

    def _pick_random(self, ct: Controller):
        print("Picking random!")
        pos = ct.get_position()
        move_dir = random.choice([d for d in DIRECTIONS if ct.is_in_vision(pos.add(d)) and is_in_bound(pos.add(d), ct) and (ct.is_tile_passable(pos.add(d)) or ct.is_tile_empty(pos.add(d)))])
        move_pos = pos.add(move_dir)
        if not is_in_bound(move_pos, ct):
            return
        self._build_road(ct, move_pos)
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
            for dx in range(-radius, radius+1):
                for dy in range(-radius, radius+1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue
                    bucket = self.buckets.get((bx + dx, by + dy))
                    if bucket:
                        candidates.extend(bucket)
            
            if candidates:
                return min_with_random_tiebreak(candidates, key=lambda c: pos.distance_squared(c))
            
            radius += 1
    
    def update_map(self, ct: Controller):
        aggression_targets = []
        position = ct.get_position()
        is_a_bitch = ct.get_current_round() >= 200 and random.random() > self.be_a_bitch_rate
        for tile in ct.get_nearby_tiles():
            env = ct.get_tile_env(tile)
            envp = env
            building_id = ct.get_tile_building_id(tile)
            bot_id = ct.get_tile_builder_bot_id(tile)
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
                    match ct.get_marker_value(building_id):
                        case 1:
                            if ct.can_build_foundry(tile) and ct.get_current_round() >= 200:
                                ct.build_foundry(tile)
                        case _: pass
                    
                    env = Environment.WALL
                    envp = env
                    
                if not same_team:
                    env = Environment.WALL
                    if etype == EntityType.CORE:
                        envp = Environment.WALL

                if (
                    self.bot_type == BOT_TYPE.AGGRESSOR and 
                    not self.aggressor_has_target and 
                    etype in CONVEYORS and
                    ct.get_stored_resource(building_id) and
                    bot_id is None
                ): 
                    if connected_to(tile, building_id, EntityType.CORE, True, ct) and not connected_to(tile, building_id, EntityType.SENTINEL, False, ct):
                        # Resource provider to the base
                        aggression_targets.append(tile)

                if etype == EntityType.HARVESTER and not same_team and self.bot_type == BOT_TYPE.AGGRESSOR and not self.aggressor_has_target:
                    for d in CARDINAL_DIRECTIONS:
                        check_pos = tile.add(d)
                        if not is_in_bound(check_pos, ct) or not ct.is_in_vision(check_pos):
                            continue
                        if (ct.is_tile_passable(check_pos) or ct.is_tile_empty(check_pos)) and not connected_to(tile, building_id, EntityType.SENTINEL, False, ct):
                            aggression_targets.append(check_pos)
                            break


            if bot_id and self.bot_type == BOT_TYPE.AGGRESSOR and tile != position:
                env = Environment.WALL
                envp = Environment.WALL


            self.internal_map[tile.x][tile.y] = env 
            self.internal_walkable_map[tile.x][tile.y] = envp
            if tile in self.unexplored:
                self.unexplored.remove(tile)
                bucket = (tile.x // self.bucket_size, tile.y // self.bucket_size)
                self.buckets[bucket].remove(tile)
                if not self.buckets[bucket]:
                    del self.buckets[bucket]  # prune empty buckets
            if env in MINEABLE:
                self.ore_sites.add(tile)
        print(aggression_targets)
        if aggression_targets and not self.aggressor_has_target and self.current_state != BOT_STATE.GOING_TO_TARGET:
            self.current_state = BOT_STATE.GOING_TO_TARGET
            self.distance_map = None
            self.current_target_pos = random.choice(aggression_targets)
            self.previous_target_pos = None
            self.aggressor_has_target = True
            self.target_distance_squared = 0
            
    def move_to_pos(self, ct: Controller):
        if not self.current_target_pos:
            return
        # start_time = ct.get_cpu_time_elapsed()
        pos = ct.get_position()

        dist_to_target = pos.distance_squared(self.current_target_pos)

        def set_wandering():
            self.current_state = BOT_STATE.WANDERING
            self.walking_back_first = False
            self.current_target_pos = None
            self.previous_target_pos = None
            self.target_distance_squared = 1
            self.distance_map = None

        match self.bot_type:
            case BOT_TYPE.INITIATORS:
                if dist_to_target <= self.target_distance_squared:
                    set_wandering()
                    return
                elif self.current_state == BOT_STATE.WANDERING and dist_to_target <= ct.get_vision_radius_sq():
                    set_wandering()
                    # Prevents idling for the rest of the round
                    if self.buckets:
                        self._random_movement(ct)
                        self.move_to_pos(ct)
                    return
            case BOT_TYPE.AGGRESSOR:
                if self.aggressor_has_target and pos == self.current_target_pos:
                    return
                if dist_to_target <= self.target_distance_squared:
                    return
            case BOT_TYPE.REPAIR:
                if dist_to_target <= self.target_distance_squared:
                    return
        
        if self.stuck_counter >= STUCK_THRESHHOLD:
            set_wandering()
            self.stuck_counter = 0
            return

        if self.previous_target_pos != self.current_target_pos or self.distance_map is None:
            self.previous_target_pos = self.current_target_pos
            self.distance_map = flood_fill(
                (self.internal_map if self.current_state == BOT_STATE.WALKING_BACK else self.internal_walkable_map),
                self.current_target_pos,
                pos,
                self.current_state != BOT_STATE.WALKING_BACK,
                self.target_distance_squared,
                self.current_state != BOT_STATE.WALKING_BACK,
                self.current_state == BOT_STATE.WALKING_BACK)
        

        decisions = [d for d in
                     (CARDINAL_DIRECTIONS if self.current_state == BOT_STATE.WALKING_BACK or
                      get_skibidi_distance(pos, self.current_target_pos) == 2
                      else DIRECTIONS)
                     if is_in_bound(pos.add(d), ct)]
        
        chosen = min(decisions, key=lambda d: get_from_dir(self.distance_map, pos, d))
        if math.isinf(get_from_dir(self.distance_map, pos, chosen)):
            # This shouldn't happen at all, but as a fail-safe:
            print("Please fix")
            # TODO FIX
            self.distance_map = None
            if self.previous_target_pos in self.ore_sites:
                self.visited_ores.add(self.previous_target_pos)
            self.previous_target_pos = None
            self.current_target_pos = None
            self._random_movement(ct)
            return
        move_pos = pos.add(chosen)

        if self.bot_type == BOT_TYPE.INITIATORS:
            bot_id = ct.get_tile_builder_bot_id(move_pos)
            if self.previous_pos == pos and bot_id:
                self.stuck_counter += 1
            else:
                self.stuck_counter = 0
            self.previous_pos = pos

        if self.walking_back_first:
            if ct.get_global_resources()[0] >= ct.get_conveyor_cost()[0] and ct.get_action_cooldown() == 0:
                if ct.can_destroy(pos):
                    building_id = ct.get_tile_building_id(pos)
                    self.walking_back_first = False
                    etype = ct.get_entity_type(building_id)
                    building_team = ct.get_team(building_id)
                    same_team = building_team == ct.get_team()
                    if (building_id and same_team and
                            (etype == EntityType.BRIDGE or etype == EntityType.SPLITTER or
                            (etype == EntityType.CONVEYOR and ct.get_direction(building_id) == chosen))
                    ): return
                    ct.destroy(pos)
                    ct.build_conveyor(pos, chosen)
            return
        
        if self.current_state == BOT_STATE.WALKING_BACK:
            if ct.get_tile_builder_bot_id(move_pos):
                # Wait
                return

            next_decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(chosen).add(d), ct)]
            next_chosen = min(next_decisions, key=lambda d: get_from_dir(self.distance_map, pos.add(chosen), d))

            if ct.can_build_conveyor(move_pos, next_chosen) and ct.get_tile_env(move_pos) not in MINEABLE:
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
                    self.walking_back_first = False
                    # set_wandering()

                else:
                    ct.destroy(move_pos)
                    if ct.can_build_conveyor(move_pos, next_chosen):
                        ct.build_conveyor(move_pos, next_chosen)

            building_id = ct.get_tile_building_id(move_pos)
            if ct.can_move(chosen) and not (building_id and ct.get_team(building_id) != ct.get_team()):
                ct.move(chosen)
            else:
                self.walking_back_first = True
                self.distance_map = None  # force repath, don't abandon target
            return
        print(move_pos)
        self._build_road(ct, move_pos)
        if ct.can_move(chosen):
            ct.move(chosen)
        elif (ct.get_tile_env(move_pos) == Environment.EMPTY and
              self.current_state != BOT_STATE.WALKING_BACK and
              ct.get_tile_builder_bot_id(move_pos)):
            self._pick_random(ct)
        else:
            self.distance_map = None  # hit a real wall, repath
    
    def _build_road(self, ct: Controller, move_pos: Position):
        direction = clamp(self.original_pos, move_pos)
        if not is_in_bound(move_pos, ct):
            return
        tile_env = ct.get_tile_env(move_pos)

        not_mineable = tile_env not in MINEABLE
        print(f"Trying to build road at {move_pos}")
        
        if self.bot_type != BOT_TYPE.AGGRESSOR and move_pos == self.original_pos.add(direction).add(direction):
            if ct.can_destroy(move_pos) and ct.get_entity_type(ct.get_tile_building_id(move_pos)) == EntityType.ROAD:
                ct.destroy(move_pos)
            if ct.can_build_splitter(move_pos, direction.opposite()) and not_mineable:
                ct.build_splitter(move_pos, direction.opposite())
        
        if (
            ct.can_build_road(move_pos) and 
            self.internal_walkable_map[move_pos.x][move_pos.y] != Environment.WALL
        ):
            ct.build_road(move_pos)

    def aggressor_script(self, ct: Controller):

        if self.bot_type != BOT_TYPE.AGGRESSOR:
            # Safety
            return
        
        def build_sentinel(p: Position, d: Direction, dy=None):
            harvester_pos = check_for_entity(p, CARDINAL_DIRECTIONS, EntityType.HARVESTER, ct)

            if harvester_pos:
                if check_for_entity(harvester_pos, CARDINAL_DIRECTIONS, EntityType.SENTINEL, ct):
                    if ct.can_build_barrier(p):
                        ct.build_barrier(p)
                        reset_target()
                    return
                
            if ct.can_build_sentinel(p, d):
                building_id = ct.get_tile_building_id(p.add(d))
                if building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER:
                    d = d.rotate_left()
                ct.build_sentinel(p, d)
                reset_target()
                return
            
        def reset_target():
            self.aggressor_has_target = False
            self.current_target_pos = None
            self.distance_map = None
            self.current_state = BOT_STATE.WANDERING
        
        position = ct.get_position()

        if not self.current_target_pos or self.current_state == BOT_STATE.WANDERING:
            self.current_target_pos = limit(Position(self.enemy_pos.x + random.randint(-5, 5), self.enemy_pos.y + random.randint(-5, 5)), ct)
        
            self.distance_map = None
            self.aggressor_has_target = False
            self.target_distance_squared = 4
            return

        building_id = ct.get_tile_building_id(self.current_target_pos) if ct.is_in_vision(self.current_target_pos) else None
        
        if (
            ct.is_in_vision(self.current_target_pos) and 
            building_id and
            ct.get_entity_type(building_id) not in PASSABLE
        ):
            reset_target()
            return

        point_dir = self.current_target_pos.direction_to(self.enemy_pos)
        can_build_sentinel = ct.get_global_resources()[0] >= ct.get_sentinel_cost()[0] and ct.get_action_cooldown() == 0
        if self.aggressor_has_target:
            if (
                not building_id or (ct.get_entity_type(building_id) == EntityType.ROAD and ct.get_team(building_id) == ct.get_team()) and
                can_build_sentinel
            ):
                if ct.can_destroy(self.current_target_pos):
                    ct.destroy(self.current_target_pos)
                
                build_sentinel(self.current_target_pos, point_dir)

                if position == self.current_target_pos:
                    self._pick_random(ct)
                    build_sentinel(self.current_target_pos, point_dir)
            
            if self.current_target_pos == position:
                if building_id and ct.get_team(building_id) != ct.get_team():
                    if ct.can_fire(position):
                        ct.fire(position)
                        if not ct.get_tile_building_id(position):
                            # We have destroyed the target
                            self._pick_random(ct)

    def initiator_script(self, ct: Controller):
        position = ct.get_position()
        global_resources = ct.get_global_resources()[0]
        bridge_cost = ct.get_bridge_cost()[0]
        action_cooldown = ct.get_action_cooldown()

        if self.visited_ores and random.random() >= self.dementia_rate:
            item = next(iter(self.visited_ores))
            self.visited_ores.remove(item)

        # Check if we have reached an ore site
        if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_harvester_cost()[0] and self.current_state != BOT_STATE.WALKING_BACK:
            if self.current_target_pos == position:
                road_pos = check_for_entity(position, CARDINAL_DIRECTIONS, EntityType.ROAD, ct)
                if road_pos and ct.can_move(road_pos):
                    ct.move(road_pos)
            for d in CARDINAL_DIRECTIONS:
                check_pos = position.add(d)
                if not is_in_bound(check_pos, ct):
                    continue
                env = ct.get_tile_env(check_pos)

                if env in MINEABLE:
                    if check_pos in self.visited_ores:
                        continue
                    building_id = ct.get_tile_building_id(check_pos)

                    if building_id and ct.get_entity_type(building_id) == EntityType.ROAD:
                        if ct.can_destroy(check_pos):
                            ct.destroy(check_pos)

                    can_build_h = ct.can_build_harvester(check_pos)
                    building_id = ct.get_tile_building_id(check_pos)
                    self.visited_ores.add(check_pos)
                    if (can_build_h or (building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER)):

                        if can_build_h:
                            ct.build_harvester(check_pos)
                        
                        self.current_state = BOT_STATE.WALKING_BACK
                        self.walking_back_first = True
                        self.current_target_pos = self.home_pos
                        self.target_distance_squared = 4
                        return True

        # Check if we reach close enough to the base
        if self.current_state == BOT_STATE.WALKING_BACK:
            if position.distance_squared(self.original_pos) <= 49:
                buildings_nearby = ct.get_nearby_buildings(9)
                team = ct.get_team()
                bridges_nearby = [
                    b for b in buildings_nearby if
                    ct.get_entity_type(b) == EntityType.SPLITTER and
                    ct.get_position(b).distance_squared(self.original_pos) <= 16 and
                    ct.get_team(b) == team
                ]

                # We are close enough to the base
                if len(bridges_nearby) >= 1:
                    bridge_id = random.choice(bridges_nearby)
                    temp_id = ct.get_tile_building_id(position)
                    
                    same_team = temp_id and ct.get_team(temp_id) == ct.get_team()
                    is_bridge = same_team and ct.get_entity_type(temp_id) in [EntityType.BRIDGE, EntityType.SPLITTER, EntityType.CORE]

                    if is_bridge or (global_resources >= bridge_cost and action_cooldown == 0):
                        if ct.can_destroy(position):
                            self.current_state = BOT_STATE.WANDERING
                            self.walking_back_first = False
                            self.current_target_pos = None
                            self.previous_target_pos = None
                            self.target_distance_squared = 1

                            if not is_bridge:
                                ct.destroy(position)
                                ct.build_bridge(position, ct.get_position(bridge_id))
                    return True

        # Go to an ore site
        if self.current_state == BOT_STATE.WANDERING:
            unvisited = self.ore_sites - self.visited_ores
            if unvisited:
                self.current_target_pos = min(unvisited, key=lambda p: position.distance_squared(p))
                self.target_distance_squared = 0 # One includes all adjacent squares
                self.current_state = BOT_STATE.GOING_TO_TARGET
                self.distance_map = None
        return None

    def repair_script(self, ct: Controller):
        if self.current_target_pos and ct.is_in_vision(self.current_target_pos):
            if ct.can_destroy(self.current_target_pos) and ct.get_entity_type(ct.get_tile_building_id(self.current_target_pos)) != EntityType.SPLITTER:
                ct.destroy(self.current_target_pos)
            if ct.can_build_splitter(self.current_target_pos,
                                     dir_to_original := self.current_target_pos.direction_to(self.original_pos)):
                ct.build_splitter(self.current_target_pos, dir_to_original)
            
        for check_dir in CARDINAL_DIRECTIONS:
            check_pos = self.original_pos.add(check_dir).add(check_dir)
            if not is_in_bound(check_pos, ct) or not ct.is_in_vision(check_pos):
                continue
            building_id = ct.get_tile_building_id(check_pos)
            if ct.get_tile_env(check_pos) == Environment.WALL or (building_id and ct.get_team(building_id) != ct.get_team()):
                continue
            if not (building_id and ct.get_entity_type(building_id) == EntityType.SPLITTER):
                self.target_distance_squared = 1
                self.current_target_pos = check_pos
                self.distance_map = None
                self.current_state = BOT_STATE.GOING_TO_TARGET
                return
        self.current_target_pos = self.original_pos
        self.target_distance_squared = 0
        self.distance_map = None
        self.current_state = BOT_STATE.GOING_TO_TARGET


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