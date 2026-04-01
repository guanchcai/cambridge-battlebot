from cambc import Controller, Environment, Position, EntityType
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class Gatherer(Bot):
    def __init__(self, ct: Controller):
        self.harvester_count = 0

        # I hate this but this variable is for one specific bug and one specific scenario
        self.build_harvester = False
        
        super().__init__(ct)

    def update_tile(self, tile, building_id, bot_id):
        can_build_harvester = self.harvester_count < 1 and self.current_state == BotState.WANDERING and tile not in self.visited_ore_sites
        
        building_entity = self.ct.get_entity_type(building_id) if building_id else None
        if self.ct.get_tile_env(tile) == Environment.ORE_TITANIUM:
            self.ore_sites.add(tile)
            if can_build_harvester:
                if building_entity == EntityType.HARVESTER:
                    pass
                else:
                    self.set_target(tile, 0, BotState.GOING_TO_TARGET)

                self.visited_ore_sites.add(tile)
        if self.current_target_position == tile and building_entity == EntityType.HARVESTER:
            self.set_wandering()

    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        print(f"Trying to build road at {move_pos}")
        def build_conveyor_chain(from_pos: Position, to_pos: Position, connect_next=True):
            building_id = self.ct.get_tile_building_id(from_pos)
            building_type = self.ct.get_entity_type(building_id) if building_id else None
            same_team = building_id and self.ct.get_team(building_id) == self.ct.get_team()
            
            if same_team and building_type in CONVEYORS:
                if self.build_harvester:
                    if build_harvester():
                        self.set_wandering()
                else:
                    self.set_wandering()
                return

            if from_pos.distance_squared(to_pos) > 1:
                if self.ct.can_build_bridge(from_pos, to_pos):
                    self.ct.build_bridge(from_pos, to_pos)
                    if connect_next:
                        self.set_target(to_pos, 0, BotState.GOING_TO_TARGET)
            elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, from_pos.direction_to(to_pos)):
                self.ct.build_conveyor(from_pos, from_pos.direction_to(to_pos))
        def build_harvester():
            potential_harvester_pos = check_for_env(self.ct, CARDINAL_DIRECTIONS, Environment.ORE_TITANIUM)
            building_entity = get_entity(potential_harvester_pos, self.ct) if potential_harvester_pos else None
            if potential_harvester_pos and potential_harvester_pos in self.visited_ore_sites:
                if building_entity is None:
                    if self.ct.can_build_harvester(potential_harvester_pos):
                        self.ct.build_harvester(potential_harvester_pos)
                    
                        self.build_harvester = False
                    return True

        
        if self.current_state != BotState.GOING_BACK:
            return super().build_road(move_pos, next_pos)

        # This runs 4 extra checks each tick idk if its good or not
        if build_harvester():
            self.set_target(self.base_position, 1, BotState.GOING_BACK)
            return False
        
        position = self.ct.get_position()
        
        current_tile_id = self.ct.get_tile_building_id(position)
        same_team = current_tile_id and self.ct.get_team(current_tile_id) == self.ct.get_team()
        if self.ct.can_fire(position) and not same_team:
            self.ct.fire(position)
        
        if self.ct.can_destroy(position) and same_team and self.ct.get_entity_type(current_tile_id) == EntityType.ROAD:
            self.ct.destroy(position)
            
        current_tile_id = self.ct.get_tile_building_id(position)

        if current_tile_id is None and self.ct.get_tile_env(position) != Environment.ORE_TITANIUM:
            build_conveyor_chain(position, move_pos)
            return False
        elif not same_team:
            return False

        if next_pos:
            build_conveyor_chain(move_pos, next_pos)
        else:
            build_conveyor_chain(move_pos, self.base_position, False)
            self.set_wandering()
        return True
    
    def run_flood_fill(self):
        match self.current_state:
            case BotState.GOING_BACK:
                self.distance_map = self.path_finder.run(
                    self.ct.get_position(),
                    self.current_target_position,
                    False, 
                    DeltaTypes.BRIDGE, 
                    self.target_distance_squared, 
                    True
                )
            case BotState.WANDERING:
                self.distance_map = self.path_finder.run(
                    self.ct.get_position(),
                    self.current_target_position,
                    True, 
                    DeltaTypes.ALL, 
                    self.target_distance_squared, 
                    False
                )
            case BotState.GOING_TO_TARGET:
                self.distance_map = self.path_finder.run(
                    self.ct.get_position(),
                    self.current_target_position,
                    True, 
                    DeltaTypes.ALL, 
                    self.target_distance_squared, 
                    True
                )
    
    def reached_target(self):
        if self.current_state == BotState.WANDERING:
            return super().reached_target()

        position = self.ct.get_position()
        env = self.ct.get_tile_env(position)
        
        building_id = self.ct.get_tile_building_id(position)
        same_team = building_id and self.ct.get_team(building_id) == self.ct.get_team()

        if building_id and not same_team:
            if self.ct.can_fire(position):
                self.ct.fire(position)

        reached_ore = self.current_state == BotState.GOING_TO_TARGET and env == Environment.ORE_TITANIUM
        can_build = self.ct.get_global_resources()[0] >= self.ct.get_harvester_cost()[0]
        can_build_bridge = self.ct.get_action_cooldown() == 0 and self.ct.get_global_resources()[0] >= self.ct.get_bridge_cost()[0]

        if reached_ore:
            for d in CARDINAL_DIRECTIONS:
                check_pos = position.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                building_entity = get_entity(check_pos, self.ct)
                if building_entity is None and self.ct.get_tile_env(check_pos) != Environment.WALL:
                    if self.ct.can_build_barrier(check_pos):
                        self.ct.build_barrier(check_pos)
                    return

        if reached_ore and can_build:
            self.set_target(self.base_position, 1, BotState.GOING_BACK)
            self.build_harvester = True
        elif self.current_state == BotState.GOING_TO_TARGET and env == Environment.EMPTY:
            if position.distance_squared(self.base_position) <= 9:
                if same_team and self.ct.can_destroy(position) and self.ct.get_entity_type(building_id) == EntityType.ROAD:
                    self.ct.destroy(position)
                building_id = self.ct.get_tile_building_id(position)
                if building_id is None:
                    if can_build_bridge:
                        self.ct.build_bridge(position, self.base_position)
                else:
                    self.set_wandering()
            else:
                self.set_target(self.base_position, 1, BotState.GOING_BACK)
    
    def nearest_unexplored(self):
        unvisited_ores = self.ore_sites - self.visited_ore_sites
        if unvisited_ores:
            to_visit = unvisited_ores.pop()
            self.visited_ore_sites.add(to_visit)
            return to_visit
        return super().nearest_unexplored()
    
    def set_wandering(self):
        next_pos = self.nearest_unexplored()
        if next_pos in self.ore_sites:
            self.set_target(next_pos, 0, BotState.GOING_TO_TARGET)
        else:
            self.set_target(next_pos, 16, BotState.WANDERING)