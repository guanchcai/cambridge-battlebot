from cambc import Controller, Environment, Position, EntityType
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class Gatherer(Bot):
    def __init__(self, ct: Controller):
        self.harvester_count = 0

        # I hate this but this variable is for one specific bug and one specific scenario
        self.build_harvester = False
        self.dont_build_wall = None

        self.previous_bot_thrower = None
        self.launcher_limit = 30
        self.launchers_built = 0
        
        super().__init__(ct)

    def update_tile(self, tile, building_id, bot_id):
        def can_pass(pos: Position):
            if not checkable_position(pos, self.ct):
                return True
            b_entity = get_entity(pos, self.ct)
            return self.ct.get_tile_env(pos) == Environment.EMPTY and (b_entity in IGNORED_BUILDINGS or b_entity in PASSABLE)
        
        can_build_harvester = self.current_state == BotState.WANDERING and tile not in self.visited_ore_sites
        
        building_entity = self.ct.get_entity_type(building_id) if building_id else None
        if self.get_from_pos(self.environment_map, tile) == Environment.ORE_TITANIUM:
            self.ore_sites.add(tile)
            if can_build_harvester:
                if building_entity == EntityType.HARVESTER:
                    pass
                else:
                    self.set_target(tile, 0, BotState.GOING_TO_TARGET)

                self.visited_ore_sites.add(tile)
        check_poses = [tile.add(d) for d in CARDINAL_DIRECTIONS] # Duplicate code
    
        if (
            self.current_state != BotState.GOING_BACK and
            self.current_target_position == tile and 
            (
                not (is_passable(tile, self.ct) or destroyable(tile, self.ct)) or \
                not any([can_pass(p) for p in check_poses])
            )
        ):
            self.set_wandering()

    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        print(f"Trying to build road at {move_pos}")
        
        position = self.ct.get_position()

        def build_conveyor_chain(from_pos: Position, to_pos: Position, connect_next=True):
            if position.distance_squared(from_pos) > 1:
                self.set_target(from_pos, 0, BotState.GOING_TO_TARGET)
                return

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
                    if not is_exposed(from_pos, self.ct) and not is_exposed(self.previous_position, self.ct) and connect_next:
                        self.set_target(to_pos, 0, BotState.GOING_TO_TARGET)
            elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, from_pos.direction_to(to_pos)):
                self.ct.build_conveyor(from_pos, from_pos.direction_to(to_pos))
        def build_harvester():
            potential_harvester_pos = check_for_env(self.ct, CARDINAL_DIRECTIONS, Environment.ORE_TITANIUM)
            building_entity = get_entity(potential_harvester_pos, self.ct) if potential_harvester_pos else None
            if potential_harvester_pos and potential_harvester_pos in self.visited_ore_sites:
                if building_entity in IGNORED_BUILDINGS:
                    if self.ct.can_build_harvester(potential_harvester_pos):
                        self.ct.build_harvester(potential_harvester_pos)
                    
                        self.build_harvester = False
                    return True
        def build_bot_thrower():
            if self.ct.get_tile_env(position) != Environment.EMPTY or get_entity(position, self.ct) is None or self.ct.get_unit_count() >= self.launcher_limit:
                return
            
            ret = False
            if is_exposed(self.previous_position, self.ct) or (is_exposed(position, self.ct) and get_entity(position, self.ct) == EntityType.BRIDGE): # Duplicate code fix later
                for d in CARDINAL_DIRECTIONS:
                    check_pos = position.add(d)
                    if not checkable_position(check_pos, self.ct) or \
                        check_pos == move_pos or \
                        self.ct.get_tile_env(check_pos) != Environment.EMPTY or \
                        get_entity(check_pos, self.ct) not in IGNORED_BUILDINGS:
                        continue
                    ret = True
                    if self.ct.can_build_launcher(check_pos):
                        self.ct.build_launcher(check_pos)
                        break
            return ret
        if checkable_position(self.current_target_position, self.ct):
            if destroyable(self.current_target_position, self.ct):
                print("Can destroy")
                if self.ct.can_destroy(self.current_target_position):
                    self.ct.destroy(self.current_target_position)
        
        if self.current_state != BotState.GOING_BACK:
            return super().build_road(move_pos, next_pos)

        # This runs 4 extra checks each tick idk if its good or not
        if build_harvester():
            self.set_target(self.base_position, 1, BotState.GOING_BACK)
            return False
        
        if build_bot_thrower():
            print("Need launchers")
            return False
        
        current_tile_id = self.ct.get_tile_building_id(position)
        same_team = current_tile_id and self.ct.get_team(current_tile_id) == self.ct.get_team()
        if self.ct.can_fire(position) and not same_team:
            self.ct.fire(position)
        
        if self.ct.can_destroy(position) and same_team and self.ct.get_entity_type(current_tile_id) == EntityType.ROAD:
            self.ct.destroy(position)
            
        current_tile_entity= get_entity(position, self.ct)

        if current_tile_entity in IGNORED_BUILDINGS and self.ct.get_tile_env(position) != Environment.ORE_TITANIUM:
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

        if reached_ore and self.dont_build_wall is None:
            path_back = self.path_finder.run(
                    position,
                    self.base_position,
                    False, 
                    DeltaTypes.BRIDGE, 
                    9, 
                    True
                )
            if len(path_back) > 1:
                self.dont_build_wall = path_back[0].direction_to(path_back[1])

        if reached_ore:
            for d in CARDINAL_DIRECTIONS:
                check_pos = position.add(d)
                if not checkable_position(check_pos, self.ct) or d == self.dont_build_wall:
                    continue
                building_entity = get_entity(check_pos, self.ct)
                if building_entity in IGNORED_BUILDINGS and self.ct.get_tile_env(check_pos) != Environment.WALL:
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
                building_entity = get_entity(position, self.ct)
                if building_entity in IGNORED_BUILDINGS:
                    if can_build_bridge:
                        self.ct.build_bridge(position, self.base_position)
                else:
                    self.set_wandering()
            else:
                self.set_target(self.base_position, 1, BotState.GOING_BACK)
        
        self.dont_build_wall = None
    
    def nearest_unexplored(self):
        unvisited_ores = self.ore_sites - self.visited_ore_sites
        if unvisited_ores:
            to_visit = min(unvisited_ores, key=lambda ore: self.ct.get_position().distance_squared(ore))
            self.visited_ore_sites.add(to_visit)
            return to_visit
        return super().nearest_unexplored()
    
    def set_wandering(self):

        next_pos = self.nearest_unexplored()
        if next_pos in self.ore_sites:
            self.set_target(next_pos, 0, BotState.GOING_TO_TARGET)

        else:
            self.set_target(next_pos, 16, BotState.WANDERING)