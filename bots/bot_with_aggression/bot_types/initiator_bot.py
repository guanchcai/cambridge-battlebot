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

        super().__init__(ct)

    def _initialisation(self, ct):
        return super()._initialisation(ct)
    
    def _set_wandering(self):
        super()._set_wandering()
        self.replace_beneath = False
    
    def _set_internal_map(self, position):
        self.distance_map = flood_fill(
            self.internal_walkable_map if self.current_state != BOT_STATE.WALKING_BACK else self.internal_map,
            self.map_width,
            self.current_target_pos,
            position, 
            ignore_ores=False,
            target_distance_squared=self.target_distance_squared,
            allow_diagonal=self.current_state != BOT_STATE.WALKING_BACK,
            bypass_wall=self.current_state == BOT_STATE.WALKING_BACK
        )
        self.print_distance_map()
    
    def _move_to_pos(self, ct: Controller):
        position = ct.get_position()
        closest_base_pos = self.original_pos.add(self.original_pos.direction_to(position))
        print(f"Distance to {closest_base_pos} is {closest_base_pos.distance_squared(position)}")
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
            self.print_distance_map()
            decisions = [d for d in
                        CARDINAL_DIRECTIONS
                        if is_in_bound(position.add(d), ct)]
            
            chosen = min(decisions, key=lambda d: get_from_dir(self.distance_map, position, d, self.map_width))
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
            return

        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            dist = get_skibidi_distance(self.current_target_pos, ct.get_position())
            building_id = ct.get_tile_building_id(self.current_target_pos) if ct.is_in_vision(self.current_target_pos) else None
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
                ) and (
                    ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_harvester_cost()[0]
                ):
                    self._pick_random(ct, CARDINAL_DIRECTIONS)
            elif dist == 1:
                if ct.get_action_cooldown() == 0 and ct.get_global_resources()[0] >= ct.get_harvester_cost()[0]:
                    if  (
                        (
                            ct.get_entity_type(building_id) in CONVEYORS or
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
                    self.target_distance_squared = 16
                    self.current_state = BOT_STATE.WALKING_BACK
                    self.current_target_pos = self.original_pos
                    self.replace_beneath = True
                    return
        
        super()._move_to_pos(ct, CARDINAL_DIRECTIONS if self.current_state == BOT_STATE.WALKING_BACK else DIRECTIONS)
            
    
    def _build_road(self, ct: Controller, move_pos, next_direction=None):
        print(f"Trying to build road at position: {move_pos}")
        if self.current_state == BOT_STATE.WALKING_BACK:
            if ct.can_destroy(move_pos):
                building_id = ct.get_tile_building_id(move_pos)
                if not (ct.get_entity_type(building_id) == EntityType.CONVEYOR and ct.get_direction(building_id) == next_direction):
                    ct.destroy(move_pos)
            if ct.can_build_conveyor(move_pos, next_direction):
                ct.build_conveyor(move_pos, next_direction)
        else:
            if ct.can_build_road(move_pos):
                ct.build_road(move_pos)
    
    def _update_tile(self, tile, building_id, ct):
        if ct.get_tile_env(tile) == Environment.ORE_TITANIUM:
            if tile not in self.ore_sites:
                self.ore_sites.add(tile)
                if self.current_state == BOT_STATE.WANDERING:
                    self.current_target_pos = self._find_target(ct)
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