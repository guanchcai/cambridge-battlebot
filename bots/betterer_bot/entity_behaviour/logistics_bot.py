from cambc import Controller, Environment, Position, EntityType
from utils.tile_info import TileData
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class LogisticsBot(Bot):
    def __init__(self, ct: Controller):
        self.harvester_count = 0
        self.titanium_harvester_count = 0

        self.axionite_ore_sites = set()
        self.pending_checks = set()

        self.current_target_type = TargetTypes.WANDER
        self.target_black_list = set()

        self.dont_build = False

        super().__init__(ct)
    
    def update_map(self):
        self.pending_checks = set()
        self.checked = set()
        return super().update_map()

    def update_tile(self, tile: Position, tile_data: TileData):  
        
        if tile_data.environment == Environment.ORE_TITANIUM:
            if tile not in self.ore_sites and self.current_target_type == TargetTypes.ORE and tile.distance_squared(self.position) < self.current_target_position.distance_squared(self.position):
                self.set_wandering()
            self.ore_sites.add(tile)
        elif tile_data.environment == Environment.ORE_AXIONITE:
            if tile not in self.axionite_ore_sites and self.harvester_count > 1 and self.current_target_type == TargetTypes.ORE and tile.distance_squared(self.position) < self.current_target_position.distance_squared(self.position):
                self.set_wandering()
            self.axionite_ore_sites.add(tile)

        if tile_data.building_type in CONVEYORS_WITHOUT_SPLITTER and tile_data.own_team:
            conveyor_target = get_conveyor_target(tile, self.ct)
            if conveyor_target and checkable_position(conveyor_target, self.ct) and conveyor_target not in self.checked:
                self.pending_checks.add(conveyor_target)

        if tile_data and tile_data.building_id and tile_data.building_type not in INVALID_CONTAINERS:
            self.pending_checks.discard(tile)
            self.checked.add(tile)

        if (
            self.current_state == BotState.GOING_TO_TARGET and
            self.current_target_position == tile
        ):
            match self.current_target_type:
                case TargetTypes.ORE:
                    if (
                        not self.is_passable(tile) or \
                        (tile_data.own_team and tile_data.building_type in CONVEYORS) or \
                        not any([self.is_passable(tile.add(d)) for d in CARDINAL_DIRECTIONS])
                    ):
                        print("Ore target not actually reachable")
                        self.set_wandering()
                case TargetTypes.CONNECT_BRIDGE:
                    if (not self.is_passable(tile)):
                        print("Bridge target not actually reachable")
                        self.set_wandering()
        

    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        print(f"Trying to build road at {move_pos} {self.current_state}")
        
        if self.build_harvester():
            print("Need harvesters")
            return False
        
        move_data = self.get_from_pos(move_pos)
        tile_data = self.get_from_pos(self.position)
        if move_data is None or tile_data is None:
            print("Not updated yet!")
            return super().build_road(move_pos, next_pos)
        
        if self.current_state == BotState.WANDERING or self.current_target_type != TargetTypes.BASE:
            print("Just building road normally")
            return super().build_road(move_pos, next_pos)
        
        enemy_team = tile_data and not tile_data.own_team
        print(self.position)

        if self.ct.can_fire(self.position) and enemy_team:
            self.ct.fire(self.position)

            # This checks if the building is still alive
            if self.ct.get_tile_building_id(self.position):
                return False
        
        new_building_id = self.ct.get_tile_building_id(self.position)
        
        if not self.dont_build and (new_building_id is None or tile_data.is_team_road()):
            self.build_conveyor_chain(self.position, move_pos)
            return False
        else:
            if self.dont_build:
                self.dont_build = False
            self.build_conveyor_chain(move_pos, next_pos)

            
        return True
    
    def unreachable_path(self):
        if self.current_state == BotState.GOING_TO_TARGET:
            self.target_black_list.add(self.current_target_position)
        return super().unreachable_path()
    
    def run_flood_fill(self):
        if self.current_target_type == TargetTypes.BASE:
            self.distance_map = self.path_finder.run(
                self.position,
                self.current_target_position,
                self.target_distance_squared,
                self.ct,
                True
            )
        else:
            self.distance_map = self.path_finder.run(
                self.position,
                self.current_target_position,
                self.target_distance_squared,
                self.ct,
                False
            )
    
    def reached_target(self):
        print(f"Reached target timer {self.ct.get_cpu_time_elapsed()}")
        if self.current_state == BotState.WANDERING or self.current_target_type == TargetTypes.BASE:
            return super().reached_target()
        self.position = self.ct.get_position()
        position_data = self.get_from_pos(self.position)
        
        target_data = self.get_from_pos(self.current_target_position)
        same_team = target_data and target_data.own_team

        if not same_team:
            if self.ct.can_fire(self.current_target_position):
                self.ct.fire(self.current_target_position)

        match self.current_target_type:
            case TargetTypes.ORE:
                for d in CARDINAL_DIRECTIONS:
                    adjacent_pos = self.position.add(d)
                    if not checkable_position(adjacent_pos, self.ct):
                        continue
                    adjacent_data = self.get_from_pos(adjacent_pos)
                    if (
                        adjacent_data and 
                        adjacent_data.environment != Environment.WALL and 
                        (adjacent_data.building_type in IGNORED_BUILDINGS or adjacent_data.is_team_road()) and
                        not adjacent_data.bot_id
                    ):
                        print(f"Building barrier at {adjacent_pos}")
                        if self.ct.can_destroy(adjacent_pos):
                            self.ct.destroy(adjacent_pos)
                        if self.ct.can_build_barrier(adjacent_pos):
                            self.ct.build_barrier(adjacent_pos)
                        return
                
                can_build = self.ct.get_global_resources()[0] >= self.ct.get_harvester_cost()[0]
                if can_build:
                    self.set_target(self.base_position, 1, BotState.GOING_TO_TARGET, TargetTypes.BASE)
                    self.dont_build = True
            case TargetTypes.CONNECT_BRIDGE:
                self.set_target(self.base_position, 1, BotState.GOING_TO_TARGET, TargetTypes.BASE)

    def nearest_unexplored(self):
        print("Finding nearest unexplored")
        unconnected = set(filter(lambda p: p not in self.target_black_list, self.pending_checks))
        if unconnected:
            to_check = next(iter(unconnected))
            self.pending_checks.remove(to_check)
            self.set_target(to_check, 0, BotState.GOING_TO_TARGET, TargetTypes.CONNECT_BRIDGE)
            print(f"Nearest unexplored is an unconnected conveyor at: {to_check}")
            return to_check

        unvisited_ores = None

        if self.harvester_count <= 1 or self.titanium_harvester_count <= 0.75 * self.harvester_count:
            unvisited_ores = self.ore_sites - self.visited_ore_sites
        else:
            unvisited_ores = self.ore_sites.union(self.axionite_ore_sites) - self.visited_ore_sites
        print(f"Unvisited: {unvisited_ores}")
        unvisited_ores = set(
            filter(
                lambda p: (
                    (self.enemy_base_pos is None) or self.base_position.distance_squared(p) <= (min(0.7 + self.ct.get_current_round() / 1500 * 0.3, 1) * max(self.map_width, self.map_height)) ** 2
                ) and not (
                    checkable_position(p, self.ct) and self.ct.get_tile_builder_bot_id(p)
                ) and p not in self.target_black_list, 
                unvisited_ores
            )
        )
        
        if unvisited_ores:
            to_visit = min(unvisited_ores, key=lambda ore: self.position.distance_squared(ore))
            self.visited_ore_sites.add(to_visit)
            print(f"I am going to visit {to_visit}")
            self.set_target(to_visit, 0, BotState.GOING_TO_TARGET, TargetTypes.ORE)

            print(f"Nearest unexplored ore is at: {to_visit}")
            return to_visit
        return None
    
    def set_wandering(self):
        print("Setting wandering")
        next_pos = self.nearest_unexplored()
        if next_pos:
            return
        else:
            next_pos = super().nearest_unexplored()
            self.set_target(next_pos, 16, BotState.WANDERING)

    def set_target(self, target_pos, distance_squared, state, target_type=TargetTypes.WANDER):
        self.current_target_type = target_type
        return super().set_target(target_pos, distance_squared, state)
    
    def build_conveyor_chain(self, from_pos: Position, to_pos: Position):
        print("Called build conveyor chain")
        from_data = self.get_from_pos(from_pos)
        if self.ct.can_destroy(from_pos) and (from_data.destroyable() or from_data.is_team_road()):
            self.ct.destroy(from_pos)

        bridge_target_pos_choices = self.get_positions_of_entities(from_pos, 9, EntityType.SPLITTER, self.team)
        p = self.ct.get_position()

        closest_base_pos = self.base_position.add(self.base_position.direction_to(from_pos))
        if bridge_target_pos_choices:
            bridge_target_pos = random.choice(bridge_target_pos_choices)
            print(f"Trying to build bridge from {from_pos} to {bridge_target_pos}")
            if self.ct.can_build_bridge(from_pos, bridge_target_pos):
                self.ct.build_bridge(from_pos, bridge_target_pos)
                self.pending_checks.discard(from_pos)
                self.set_wandering()
            elif from_data.building_type in CONVEYORS and from_data.own_team:
                self.pending_checks.discard(from_pos)
                self.set_wandering()

            return
        elif from_pos.distance_squared(closest_base_pos) <= 9:
            print(f"Trying to build bridge from {from_pos} to {closest_base_pos}")
            if self.ct.can_build_bridge(from_pos, closest_base_pos):
                self.ct.build_bridge(from_pos, closest_base_pos)
                self.pending_checks.discard(from_pos)
                self.set_wandering()
            elif from_data.building_type in CONVEYORS and from_data.own_team:
                self.pending_checks.discard(from_pos)
                self.set_wandering()
            return

        print(f"Building conveyor chain from {from_pos} to {to_pos}")

        same_team = from_data and from_data.own_team
        
        if same_team and from_data.building_type in CONVEYORS:
            print("Reached existing chain")

            self.set_wandering()
            return
        
        dir = from_pos.direction_to(to_pos)
        if from_pos.distance_squared(to_pos) > 1 or get_skibidi_distance(to_pos, self.base_position) == 2:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)
                
                self.set_target(to_pos, 0, BotState.GOING_TO_TARGET, TargetTypes.CONNECT_BRIDGE)
        elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, dir):
            if not from_data.bot_id or from_data.bot_id == self.id:
                self.ct.build_conveyor(from_pos, dir)
    
    def build_harvester(self, p=None):
        potential_harvester_pos = p or self.previous_position
        
        if not potential_harvester_pos or potential_harvester_pos not in self.visited_ore_sites:
            return
        tile_data = self.get_from_pos(potential_harvester_pos)
        
        if tile_data and tile_data.environment in ORE_SITES and (tile_data.building_type in IGNORED_BUILDINGS or tile_data.is_team_road()):
            print("Reached here")
            if self.ct.can_destroy(potential_harvester_pos):
                self.ct.destroy(potential_harvester_pos)
            if self.ct.can_build_harvester(potential_harvester_pos):
                self.ct.build_harvester(potential_harvester_pos)
                self.harvester_count += 1
                if tile_data.environment == Environment.ORE_TITANIUM:
                    self.titanium_harvester_count += 1
            return True
            