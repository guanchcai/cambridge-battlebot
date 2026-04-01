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

        super().__init__(ct)

    def _initialisation(self, ct):
        return super()._initialisation(ct)
    
    def _set_wandering(self):
        super()._set_wandering()
        self.replace_beneath = False
    
    def _set_internal_map(self, position):
        if not self.current_target_pos:
            print("No target position!")
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
                True,
                self.target_distance_squared,
                True,
                False
            )
        
        print(self.distance_map)
    
    def _move_to_pos(self, ct: Controller):
        position = ct.get_position()
        closest_base_pos = self.original_pos.add(self.original_pos.direction_to(position))
        building_id = ct.get_tile_building_id(self.current_target_pos) if self.current_target_pos and ct.is_in_vision(self.current_target_pos) else None
        if self.current_state == BOT_STATE.WALKING_BACK or self.current_state == BOT_STATE.GOING_TO_TARGET:
            current_id = ct.get_tile_building_id(position)
            if (
                current_id and 
                ct.get_team(current_id) != ct.get_team() and
                ct.can_fire(position)
            ):
                ct.fire(position)

        if closest_base_pos.distance_squared(position) <= 9 and self.current_state == BOT_STATE.WALKING_BACK:
            building_id = ct.get_tile_building_id(position)
            is_bridge = building_id and ct.get_entity_type(building_id) == EntityType.BRIDGE

            if not is_bridge:
                can_afford = ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_bridge_cost()[0]
                if not can_afford:
                    return

                if building_id:
                    if ct.can_destroy(position):
                        ct.destroy(position)

                if ct.can_build_bridge(position, closest_base_pos):
                    ct.build_bridge(position, closest_base_pos)
                    self.replace_beneath = False

            self._set_wandering()
            return

        if self.replace_beneath:
            self._set_internal_map(position)
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
                                
            else:
                chosen = self.distance_map[0]
                building_id = ct.get_tile_building_id(position)
                if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_bridge_cost()[0] and \
                    not (building_id and ct.get_entity_type(building_id) == EntityType.BRIDGE and ct.get_team(building_id) == ct.get_team()):
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
                        
                        self.current_state = BOT_STATE.GOING_TO_TARGET
                        self.current_target_pos = chosen
                        self.previous_target_pos = None
                        self.target_distance_squared = 0
                        self.distance_map = None

            return

        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            dist = get_skibidi_distance(self.current_target_pos, position)
            
            if dist == 0:                
                building_id = ct.get_tile_building_id(self.current_target_pos)
                if (
                    building_id is None or 
                    (
                        ct.get_entity_type(building_id) == EntityType.ROAD and 
                        ct.get_team(building_id) == ct.get_team()
                    )
                ):
                    if ct.get_tile_env(self.current_target_pos) in MINEABLE:
                        if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_harvester_cost()[0]:
                            self._pick_random(ct, CARDINAL_DIRECTIONS)
                    else:
                        print("Trying to connect a bridge")
                        self.target_distance_squared = 0
                        self.current_state = BOT_STATE.WALKING_BACK
                        self.current_target_pos = self.original_pos
                        self.replace_beneath = True
                        return
            elif dist == 1 and ct.get_tile_env(self.current_target_pos) in MINEABLE:
                can_afford = ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_harvester_cost()[0]
                already_harvesting = building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER
                own_building = (
                    building_id and
                    ct.get_entity_type(building_id) != EntityType.HARVESTER and
                    ct.get_team(building_id) == ct.get_team()
                )

                if already_harvesting or (can_afford and (own_building or building_id is None)):
                    if can_afford and not already_harvesting:
                        if own_building:
                            ct.destroy(self.current_target_pos)

                        if ct.get_tile_building_id(self.current_target_pos) is None:
                            ct.build_harvester(self.current_target_pos)

                    self.visited_ores.add(self.current_target_pos)
                    self.target_distance_squared = 0
                    self.current_state = BOT_STATE.WALKING_BACK
                    self.current_target_pos = self.original_pos
                    self.replace_beneath = True
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
        if self.current_state == BOT_STATE.WALKING_BACK and not self.replace_beneath:
            next_position = self.distance_map[0] if move_pos != self.distance_map[0] else self.distance_map[1]
            if get_skibidi_distance(next_position, move_pos) == 1:
                next_direction = move_pos.direction_to(next_position)
                if ct.can_destroy(move_pos):
                    building_id = ct.get_tile_building_id(move_pos)
                    if ct.get_entity_type(building_id) not in [EntityType.CONVEYOR, EntityType.ROAD, EntityType.MARKER]:
                        self._set_wandering()
                        return
                    if not (ct.get_entity_type(building_id) == EntityType.CONVEYOR and ct.get_direction(building_id) == next_direction):
                        ct.destroy(move_pos)
                if ct.can_build_conveyor(move_pos, next_direction):
                    ct.build_conveyor(move_pos, next_direction)
            else:
                if ct.can_destroy(move_pos):
                    building_id = ct.get_tile_building_id(move_pos)
                    if ct.get_entity_type(building_id) not in [EntityType.BRIDGE, EntityType.HARVESTER]:
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
                if building_id and ct.get_entity_type(building_id) == EntityType.HARVESTER:
                    self.visited_ores.add(tile)
                    self._set_wandering()
                elif building_id and ct.get_entity_type(building_id) not in PASSABLE and ct.get_team(building_id) == ct.get_team():
                    self.target_distance_squared = 1
                    self.distance_map = None
                
            if tile not in self.ore_sites:
                self.ore_sites.add(tile)
                if self.current_state == BOT_STATE.WANDERING:
                    if  (
                        building_id is None or 
                        ct.get_entity_type(building_id) == EntityType.HARVESTER or
                        ct.get_entity_type(building_id) in PASSABLE
                    ):
                        self.target_distance_squared = 1 if ct.get_entity_type(building_id) == EntityType.HARVESTER else 0
                        self.current_state = BOT_STATE.GOING_TO_TARGET
                        self.current_target_pos = self._find_target(ct)
                        self.distance_map = None
                    else:
                        self.visited_ores.add(tile)
        if building_id and ct.get_entity_type(building_id) == EntityType.BRIDGE and self.current_state == BOT_STATE.WANDERING and ct.get_team(building_id) == ct.get_team():
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
        bot_id = ct.get_tile_builder_bot_id(wall_pos)
        if bot_id and self.current_state != BOT_STATE.WALKING_BACK:
            self._pick_random(ct)
            self.distance_map = None
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