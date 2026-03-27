from bot_types.bot import Bot, BOT_STATE
from path_finder_two import flood_fill
from player_utils import *

class Initator(Bot):
    def __init__(self, ct: Controller):
        # Unique variables
        self.stuck_counter = 0
        self.replace_beneath = False
        self.ore_sites = set()
        self.visited_ores = set()

        self.previous_pos = None
        self.wall_building = False

        super().__init__(ct)

    def _initialisation(self, ct):
        return super()._initialisation(ct)
    
    def _set_wandering(self):
        super()._set_wandering()
        self.replace_beneath = False
    
    def _set_internal_map(self, position):
        if not self.current_target_pos:
            return
        if self.current_state == BOT_STATE.WALKING_BACK:
            self.distance_map = self.placeable_calculator.run(
                self.current_target_pos,
                position,
                False,
                self.target_distance_squared,
                False,
                True
            )
        else:
            self.distance_map = self.walkable_calculator.run(
                self.current_target_pos,
                position,
                False,
                self.target_distance_squared,
                True,
                False
            )
        
        if not self.distance_map:
            print("Something is wrong")
    
    def _move_to_pos(self, ct: Controller):
        position = ct.get_position()
        closest_base_pos = self.original_pos.add(self.original_pos.direction_to(position))
        if closest_base_pos.distance_squared(position) <= 9 and self.current_state == BOT_STATE.WALKING_BACK:
            building_id = ct.get_tile_building_id(position)
            if building_id and ct.get_entity_type(building_id) != EntityType.BRIDGE: 
                if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_bridge_cost()[0]:
                    if ct.can_destroy(position):
                        ct.destroy(position)
                    elif ct.can_fire(position):
                        ct.fire(position)
                    
                    if ct.can_build_bridge(position, closest_base_pos):
                        ct.build_bridge(position, closest_base_pos)
                        self.replace_beneath = False
                        self._set_wandering()
            return

        if self.replace_beneath:
            self._set_internal_map(position)
            print(self.current_target_pos)
            if position == self.distance_map[0]:
                self.distance_map.pop(0)
            if not self.distance_map:
                return
            if get_skibidi_distance(position, self.distance_map[0]) == 1:
                chosen = position.direction_to(self.distance_map[0])
                if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_conveyor_cost()[0]:
                    building_id = ct.get_tile_building_id(position)
                    self.replace_beneath = False
                    if building_id:
                        match ct.get_entity_type(building_id):
                            case EntityType.ROAD:
                                if ct.can_destroy(position):
                                    ct.destroy(position)
                                    ct.build_conveyor(position, chosen)
                            case EntityType.CONVEYOR:
                                if ct.get_direction(building_id) != chosen:
                                    ct.destroy(position)
                                    ct.build_conveyor(position, chosen)
                            case EntityType.BRIDGE:
                                self._set_wandering()
                                return
            else:
                chosen = self.distance_map[0]
                if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_bridge_cost()[0]:
                    building_id = ct.get_tile_building_id(position)
                    self.replace_beneath = False
                    if building_id:
                        match ct.get_entity_type(building_id):
                            case EntityType.ROAD | EntityType.CONVEYOR:
                                if ct.can_destroy(position):
                                    ct.destroy(position)
                                    ct.build_bridge(position, chosen)
                            case EntityType.BRIDGE:
                                if ct.get_bridge_target(building_id) != chosen:
                                    ct.destroy(position)
                                    ct.build_bridge(position, chosen)
                        print("YO I BUILT A BRIDGE IM BOUTTA BUUUUST")
                        self._set_wandering()

            return

        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            dist = get_skibidi_distance(self.current_target_pos, ct.get_position())
            building_id = ct.get_tile_building_id(self.current_target_pos) if ct.is_in_vision(self.current_target_pos) else None
            if self.wall_building and building_id and ct.get_entity_type(building_id) != EntityType.ROAD:
                self.wall_building = False
                self._set_wandering()
                print("Already has a wall there")
                return
            
            if dist == 0:
                if (
                    building_id and 
                    ct.get_team(building_id) != ct.get_team() and
                    ct.can_fire(self.current_target_pos)
                ):
                    ct.fire(self.current_target_pos)
                
                b_id = ct.get_tile_building_id(self.current_target_pos)
                if (
                    b_id is None or 
                    (
                        ct.get_entity_type(building_id) == EntityType.ROAD and 
                        ct.get_team(building_id) == ct.get_team()
                    )
                ):
                    if ct.get_tile_env(self.current_target_pos) in MINEABLE:
                        if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_harvester_cost()[0]:
                            self._pick_random(ct, CARDINAL_DIRECTIONS)
                    elif self.wall_building:
                        if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_barrier_cost()[0]:
                            self._pick_random(ct, CARDINAL_DIRECTIONS)
                    else:
                        print("Trying to connect a bridge")
                        self.target_distance_squared = 0
                        self.current_state = BOT_STATE.WALKING_BACK
                        self.current_target_pos = self.original_pos
                        self.replace_beneath = True
                        return
            elif dist == 1 and ct.get_tile_env(self.current_target_pos) in MINEABLE:
                if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_harvester_cost()[0]:
                    if  (
                        (
                            # ct.get_entity_type(building_id) in CONVEYORS or
                            ct.get_entity_type(building_id) == EntityType.ROAD
                        ) and 
                        ct.get_team(building_id) == ct.get_team()
                    ):
                        ct.destroy(self.current_target_pos)
                    building_id = ct.get_tile_building_id(self.current_target_pos)
                    if (
                        building_id is None
                    ):
                        ct.build_harvester(self.current_target_pos)
                    self.visited_ores.add(self.current_target_pos)
                    self.target_distance_squared = 0
                    self.current_state = BOT_STATE.WALKING_BACK
                    self.current_target_pos = self.original_pos
                    self.replace_beneath = True
                    return
                elif building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER:
                    self.visited_ores.add(self.current_target_pos)
                    self.target_distance_squared = 0
                    self.current_state = BOT_STATE.WALKING_BACK
                    self.current_target_pos = self.original_pos
                    self.replace_beneath = True
                    return
            elif dist == 1 and self.wall_building:
                if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_barrier_cost()[0]:
                    if  (
                        (
                            # ct.get_entity_type(building_id) in CONVEYORS or
                            ct.get_entity_type(building_id) == EntityType.ROAD
                        ) and 
                        ct.get_team(building_id) == ct.get_team()
                    ):
                        ct.destroy(self.current_target_pos)
                    building_id = ct.get_tile_building_id(self.current_target_pos)
                    if (
                        building_id is None and ct.can_build_barrier(self.current_target_pos)
                    ):
                        ct.build_barrier(self.current_target_pos)
                        self.wall_building = False
                        self._set_wandering()
                    return


        
        super()._move_to_pos(ct, CARDINAL_DIRECTIONS if self.current_state == BOT_STATE.WALKING_BACK else DIRECTIONS)

        if self.previous_pos == position and position != self.current_target_pos and self.current_state != BOT_STATE.WALKING_BACK:
            self.stuck_counter += 1
        else:
            self.stuck_counter = 0
        
        self.previous_pos = position

        if self.stuck_counter >= 3:
            self._pick_random(ct)
            
    
    def _build_road(self, ct: Controller, move_pos):
        print(f"Trying to build road at position: {move_pos}")
        if self.current_state == BOT_STATE.WALKING_BACK:
            next_position = self.distance_map[0] if move_pos != self.distance_map[0] else self.distance_map[1]
            if get_skibidi_distance(next_position, move_pos) == 1:
                next_direction = move_pos.direction_to(next_position)
                if ct.can_destroy(move_pos):
                    building_id = ct.get_tile_building_id(move_pos)
                    if ct.get_entity_type(building_id) == EntityType.BRIDGE:
                        self._set_wandering()
                        return
                    if not (ct.get_entity_type(building_id) == EntityType.CONVEYOR and ct.get_direction(building_id) == next_direction):
                        ct.destroy(move_pos)
                if ct.can_build_conveyor(move_pos, next_direction):
                    ct.build_conveyor(move_pos, next_direction)
            else:
                if ct.can_destroy(move_pos):
                    building_id = ct.get_tile_building_id(move_pos)
                    if not (ct.get_entity_type(building_id) == EntityType.BRIDGE and ct.get_bridge_target(building_id) == next_position):
                        ct.destroy(move_pos)
                if ct.can_build_bridge(move_pos, next_position):
                    ct.build_bridge(move_pos, next_position)
                    self._set_wandering()

        else:
            if ct.can_build_road(move_pos):
                ct.build_road(move_pos)
    
    def _update_tile(self, tile, building_id, ct):
        if ct.get_tile_env(tile) == Environment.ORE_TITANIUM:
            if tile == self.current_target_pos:
                bot_id = ct.get_tile_builder_bot_id(tile)
                if bot_id and bot_id != ct.get_id():
                    self.visited_ores.add(tile)
                    self._set_wandering()
            if tile not in self.ore_sites:
                self.ore_sites.add(tile)
                if self.current_state == BOT_STATE.WANDERING:
                    if  (
                        building_id is None or 
                        ct.get_entity_type(building_id) == EntityType.HARVESTER or
                        ct.get_entity_type(building_id) in PASSABLE
                    ):
                        self.target_distance_squared = 1 if ct.get_entity_type(building_id) == EntityType.HARVESTER else 0
                        self.current_target_pos = self._find_target(ct)
                        self.current_state = BOT_STATE.GOING_TO_TARGET
                        self.distance_map = None
                    else:
                        self.visited_ores.add(tile)
            if building_id and self.current_state == BOT_STATE.WANDERING and ct.get_entity_type(building_id) == EntityType.HARVESTER and ct.get_team(building_id) == ct.get_team():
                for d in CARDINAL_DIRECTIONS:
                    check_pos = tile.add(d)
                    if not (is_in_bound(check_pos, ct) and ct.is_in_vision(check_pos)) or ct.get_tile_env(check_pos) != Environment.EMPTY:
                        continue
                    check_id = ct.get_tile_building_id(check_pos)
                    if check_id is None or ct.get_entity_type(check_id) == EntityType.ROAD:
                        self.current_target_pos = check_pos
                        self.target_distance_squared = 0
                        self.current_state = BOT_STATE.GOING_TO_TARGET
                        self.distance_map = None
                        self.wall_building = True
                        return
        elif building_id and ct.get_entity_type(building_id) == EntityType.BRIDGE and self.current_state == BOT_STATE.WANDERING:
            target_pos = ct.get_bridge_target(building_id)
            if not (ct.is_in_vision(target_pos) and is_in_bound(target_pos, ct)):
                return
            target_id = ct.get_tile_building_id(target_pos)
            if not target_id or ct.get_entity_type(target_id) in INVALID_CONTAINERS:
                self.current_target_pos = target_pos
                self.target_distance_squared = 0
                self.current_state = BOT_STATE.GOING_TO_TARGET
                self.distance_map = None
            
                        

    def _find_target(self, ct):
        unexplored_ores = self.ore_sites - self.visited_ores
        if unexplored_ores:
            self.target_distance_squared = 0
            self.current_state = BOT_STATE.GOING_TO_TARGET
            return unexplored_ores.pop()
        self.current_state = BOT_STATE.WANDERING
        self.target_distance_squared = 16
        return self._nearest_unexplored(ct.get_position())
    
    def _read_markers(self, val, marker_pos):
        pass

    def _hit_wall(self, wall_pos, ct):
        print("I hit a wall!")
        print(wall_pos)
        building_id = ct.get_tile_building_id(wall_pos)
        if get_from_pos(self.internal_walkable_map, wall_pos, self.map_width) != Environment.WALL and self.current_state != BOT_STATE.WALKING_BACK:
            self._pick_random(ct)
            return
        if self.current_state == BOT_STATE.WALKING_BACK:
            self.replace_beneath = True
        
        self.distance_map = None
        

    def _target_reached(self, ct):
        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            return
        elif self.current_state == BOT_STATE.WALKING_BACK:
            self._set_wandering()

        else:
            self.current_target_pos = self._find_target(ct)
            self._move_to_pos(ct)