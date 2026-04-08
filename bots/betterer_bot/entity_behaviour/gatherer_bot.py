from cambc import Controller, Environment, Position, EntityType
from utils.tile_info import TileData
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class Gatherer(Bot):
    def __init__(self, ct: Controller):
        self.harvester_count = 0

        self.axionite_ore_sites = set()

        self.target_type = None

        super().__init__(ct)

    def update_tile(self, tile: Position, tile_data: TileData):                
        if tile_data.environment == Environment.ORE_TITANIUM:
            self.ore_sites.add(tile)
        elif tile_data.environment == Environment.ORE_AXIONITE:
            self.axionite_ore_sites.add(tile)
    
        if (
            self.current_state == BotState.GOING_TO_TARGET and
            self.current_target_position == tile
        ):
            if tile_data.bot_id != self.ct.get_id() and tile_data.bot_team == self.team:
                self.set_wandering()
            elif (
                not (tile_data.passable() or tile_data.destroyable(self.team)) or \
                not any([self.is_passable(tile.add(d)) for d in CARDINAL_DIRECTIONS])
            ):
                print("Yeah no fuh that")
                self.set_wandering()
        

    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        print(f"Trying to build road at {move_pos} {self.current_state}")
        move_data = self.get_from_pos(move_pos)
        tile_data = self.get_from_pos(self.position)

        if checkable_position(self.current_target_position, self.ct):
            if move_data.destroyable(self.team):
                print("Can destroy")
                if self.ct.can_destroy(self.current_target_position):
                    self.ct.destroy(self.current_target_position)
        
        if self.current_state != BotState.GOING_BACK:
            return super().build_road(move_pos, next_pos)

        # This runs 4 extra checks each tick idk if its good or not
        if self.build_harvester(self.position):
            print("Need harvesters")
            return False

        same_team = tile_data and tile_data.building_team == self.team
        if self.ct.can_fire(self.position) and not same_team:
            self.ct.fire(self.position)

            # This checks if the building is still alive
            if self.ct.get_tile_building_id(self.position):
                return False
        
        new_building_id = self.ct.get_tile_building_id(self.position)

        if (new_building_id is None or tile_data.is_team_road(self.team)) and tile_data.environment not in ORE_SITES:
            self.build_conveyor_chain(self.position, move_pos)
            return False
        elif next_pos:
            self.build_conveyor_chain(move_pos, next_pos)
            
        return True
    
    def run_flood_fill(self):
        match self.current_state:
            case BotState.GOING_BACK:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    False, 
                    DeltaTypes.BRIDGE, 
                    0, 
                    True
                )
            case BotState.WANDERING:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    True, 
                    DeltaTypes.ALL, 
                    self.target_distance_squared, 
                    False
                )
            case BotState.GOING_TO_TARGET:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    True, 
                    DeltaTypes.ALL, 
                    self.target_distance_squared, 
                    True
                )
    
    def reached_target(self):
        if self.current_state == BotState.WANDERING:
            return super().reached_target()
        self.position = self.ct.get_position()
        position_data = self.get_from_pos(self.position)
        target_data = self.get_from_pos(self.current_target_position)
        same_team = target_data and target_data.building_team == self.team

        if not same_team:
            if self.ct.can_fire(self.current_target_position):
                self.ct.fire(self.current_target_position)

        reached_ore = self.current_state == BotState.GOING_TO_TARGET and target_data.environment in ORE_SITES
        can_build = self.ct.get_global_resources()[0] >= self.ct.get_harvester_cost()[0]
        
        if reached_ore:
            for d in CARDINAL_DIRECTIONS:
                check_pos = self.position.add(d)
                if not checkable_position(check_pos, self.ct) or d == self.position.direction_to(self.previous_position):
                    continue
                tile_data = self.get_from_pos(check_pos)
                if tile_data.bot_id:
                    continue
                if (tile_data.building_type in IGNORED_BUILDINGS or tile_data.is_team_road(self.team)) and tile_data.environment != Environment.WALL:
                    if self.ct.can_destroy(check_pos):
                        self.ct.destroy(check_pos)
                    if self.ct.can_build_barrier(check_pos):
                        self.ct.build_barrier(check_pos)
                        return

        if reached_ore and can_build:
            self.set_target(self.base_position, BASE_DIST, BotState.GOING_BACK, TargetTypes.BASE)
            
        elif self.current_state == BotState.GOING_TO_TARGET and target_data.environment == Environment.EMPTY:
            if self.position.distance_squared(self.base_position) <= BASE_DIST:
                if self.ct.can_destroy(self.current_target_position) and target_data.is_team_road(self.team):
                    self.ct.destroy(self.current_target_position)
                    
                if target_data.building_type in IGNORED_BUILDINGS:
                    bridge_target_pos_choices = self.get_positions_of_entities(self.current_target_position, 9, EntityType.SPLITTER, self.team)
                    bridge_target_pos = random.choice(bridge_target_pos_choices) if bridge_target_pos_choices else None
                    if bridge_target_pos and self.ct.can_build_bridge(self.position, bridge_target_pos):
                        self.ct.build_bridge(self.position, bridge_target_pos)
                
                if target_data.building_type in CONVEYORS and same_team:
                    self.set_wandering()
            else:
                self.set_target(self.base_position, BASE_DIST, BotState.GOING_BACK, TargetTypes.BASE)
        
    
    def nearest_unexplored(self):
        if self.launchers_built >= self.launcher_limit:
            return None
        unvisited_ores = None
        if self.harvester_count <= 3:
            unvisited_ores = self.ore_sites - self.visited_ore_sites
        else:
            unvisited_ores = self.ore_sites.union(self.ignored_ore_sites) - self.visited_ore_sites
        print(f"Unvisited: {unvisited_ores}")
        unvisited_ores = set(
            filter(
                lambda p: (
                    (self.enemy_base_pos is None) or self.base_position.distance_squared(p) <= 1.3 * self.enemy_base_pos.distance_squared(p)
                ) and not (
                    checkable_position(p, self.ct) and self.ct.get_tile_builder_bot_id(p)
                ), 
                unvisited_ores
            )
        )
        
        if unvisited_ores:
            to_visit = min(unvisited_ores, key=lambda ore: self.position.distance_squared(ore))
            self.visited_ore_sites.add(to_visit)
            print(f"I am going to visit {to_visit}")
            return to_visit
        return None
    
    def set_wandering(self):
        next_pos = self.nearest_unexplored()
        if next_pos:
            self.set_target(next_pos, 0, BotState.GOING_TO_TARGET, TargetTypes.ORE)
        else:
            next_pos = super().nearest_unexplored()
            self.set_target(next_pos, 16, BotState.WANDERING, None)

    def set_target(self, target_pos, distance_squared, state, target_type):
        self.target_type = target_type
        return super().set_target(target_pos, distance_squared, state)
    
    
    def build_conveyor_chain(self, from_pos: Position, to_pos: Position, connect_next=True):
        from_data = self.get_from_pos(from_pos)
        if self.ct.can_destroy(from_pos) and from_data.destroyable(self.team):
            self.ct.destroy(from_pos)

        bridge_target_pos_choices = self.get_positions_of_entities(from_pos, 9, EntityType.SPLITTER, self.team)
        
        if bridge_target_pos_choices:
            bridge_target_pos = random.choice(bridge_target_pos_choices)
            to_pos = bridge_target_pos
        elif from_pos.distance_squared(self.base_position) <= BASE_DIST and not bridge_target_pos_choices:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)
        to_data = self.get_from_pos(to_pos)                

        print(f"Building conveyor chain from {from_pos} to {to_pos}")
        if self.position.distance_squared(from_pos) > 1:
            print("Too far away!")
            self.set_target(from_pos, 0, BotState.GOING_TO_TARGET)
            return

        same_team = from_data and from_data.building_team == self.team
        
        if same_team and from_data.building_type in CONVEYORS:
            print("Reached existing chain")

            p = self.ct.get_position()
            if not self.build_harvester(p):
                self.set_wandering()
            return

        if from_pos.distance_squared(to_pos) > 1 or get_skibidi_distance(to_pos, self.base_position) == 2:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)

                if connect_next and not self.build_harvester(self.ct.get_position()):
                    print("I should set target?")
                    self.set_target(to_pos, 0, BotState.GOING_TO_TARGET, TargetTypes.CONNECT_BRIDGE)
        elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, from_pos.direction_to(to_pos)):
            bot_id = self.ct.get_tile_builder_bot_id(from_pos)
            if not bot_id:
                self.ct.build_conveyor(from_pos, from_pos.direction_to(to_pos))
    
    def build_harvester(self, position):
        potential_harvester_pos = None
        for d in CARDINAL_DIRECTIONS:
            check_pos = position.add(d)
            print(f"Checking {check_pos} for harvester potential")
            if not checkable_position(check_pos, self.ct):
                continue
            if self.ct.get_tile_env(check_pos) in ORE_SITES and check_pos in self.visited_ore_sites:
                potential_harvester_pos = check_pos
                break
        
        print(potential_harvester_pos)
        building_entity = get_entity(potential_harvester_pos, self.ct) if potential_harvester_pos else None
        if potential_harvester_pos and potential_harvester_pos in self.visited_ore_sites:
            if building_entity in IGNORED_BUILDINGS or is_team_road(potential_harvester_pos, self.ct):
                if self.ct.can_destroy(potential_harvester_pos):
                    self.ct.destroy(potential_harvester_pos)
                if self.ct.can_build_harvester(potential_harvester_pos):
                    self.ct.build_harvester(potential_harvester_pos)
                    self.harvester_count += 1
                return True
            
    def build_bot_thrower(self, position, move_pos):
        return False