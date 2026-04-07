from cambc import Controller, Environment, Position, EntityType
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class Gatherer(Bot):
    def __init__(self, ct: Controller):
        self.harvester_count = 0

        # I hate this pt 2
        self.just_bridged = False

        self.dont_build_wall = None

        self.previous_bot_thrower = None
        self.launcher_limit = 20
        self.launchers_built = 0
        self.ignored_ore_sites = set()

        self.target_type = None

        super().__init__(ct)

    def update_tile(self, tile, building_id, bot_id):
        def can_pass(pos: Position):
            if not checkable_position(pos, self.ct):
                return True
            b_entity = get_entity(pos, self.ct)
            return self.ct.get_tile_env(pos) != Environment.WALL and (b_entity in IGNORED_BUILDINGS or b_entity in PASSABLE)
                
        if self.get_from_pos(self.environment_map, tile) == Environment.ORE_TITANIUM:
            self.ore_sites.add(tile)
            if self.current_state == BotState.GOING_TO_TARGET and self.target_type == TargetTypes.ORE:
                self.visited_ore_sites.discard(self.current_target_position)
                self.set_wandering()
        elif self.get_from_pos(self.environment_map, tile) == Environment.ORE_AXIONITE:
            self.ignored_ore_sites.add(tile)
    
        if (
            self.current_state != BotState.GOING_BACK and
            self.current_target_position == tile and 
            (
                not (is_passable(tile, self.ct) or destroyable(tile, self.ct)) or \
                not any([can_pass(tile.add(d)) for d in CARDINAL_DIRECTIONS])
            )
        ):
            print("Yeah no fuh that")
            self.set_wandering()
        

    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        print(f"Trying to build road at {move_pos}")

        if checkable_position(self.current_target_position, self.ct):
            if destroyable(self.current_target_position, self.ct):
                print("Can destroy")
                if self.ct.can_destroy(self.current_target_position):
                    self.ct.destroy(self.current_target_position)
        
        if self.current_state != BotState.GOING_BACK and self.target_type != TargetTypes.CONNECT_BRIDGE:
            return super().build_road(move_pos, next_pos)

        # This runs 4 extra checks each tick idk if its good or not
        if self.build_harvester(self.position):
            print("Need harvesters")
            return False
        
        if self.build_bot_thrower(self.position, move_pos):
            print("Need launchers")
            return False
        
        if self.just_bridged:
            print("I just bridged!")
            self.just_bridged = False
            self.set_wandering()
            return True
        
        if self.current_state == BotState.GOING_TO_TARGET:
            return super().build_road(move_pos, next_pos)

        current_tile_id = self.ct.get_tile_building_id(self.position)
        same_team = current_tile_id and self.ct.get_team(current_tile_id) == self.ct.get_team()
        if self.ct.can_fire(self.position) and not same_team:
            self.ct.fire(self.position)
            
        current_tile_entity = get_entity(self.position, self.ct)
        
        if current_tile_id and not same_team:
            return False

        if (current_tile_entity is None or is_team_road(self.position, self.ct)) and self.ct.get_tile_env(self.position) not in ORE_SITES:
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
        env = self.ct.get_tile_env(self.position)
        
        building_id = self.ct.get_tile_building_id(self.position)
        same_team = building_id and self.ct.get_team(building_id) == self.ct.get_team()

        if building_id and not same_team:
            if self.ct.can_fire(self.position):
                self.ct.fire(self.position)

        reached_ore = self.current_state == BotState.GOING_TO_TARGET and env in ORE_SITES
        can_build = self.ct.get_global_resources()[0] >= self.ct.get_harvester_cost()[0] + self.ct.get_bridge_cost()[0]
        
        if reached_ore and (self.dont_build_wall is None or self.get_from_pos(self.internal_map, self.position.add(self.dont_build_wall)) == Environment.WALL):
            candidate = []
            for d in CARDINAL_DIRECTIONS:
                check_pos = self.position.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                env = self.ct.get_tile_env(check_pos)
                if env != Environment.EMPTY:
                    continue
                if check_pos.distance_squared(self.base_position) <= 8:
                    continue

                b_id = self.ct.get_tile_building_id(check_pos)
                b_entity = self.ct.get_entity_type(b_id) if b_id else None
                b_same_team = self.ct.get_team(b_id) == self.team
                if is_team_road(check_pos, self.ct) or b_entity in IGNORED_BUILDINGS:
                    candidate.append(d)
                if b_entity in CONVEYORS and b_same_team:
                    self.dont_build_wall = d
            if not self.dont_build_wall and candidate:
                self.dont_build_wall = candidate.pop()
                
            if not self.dont_build_wall:
                self.set_wandering()
                return
            
        if reached_ore:
            for d in CARDINAL_DIRECTIONS:
                check_pos = self.position.add(d)
                if not checkable_position(check_pos, self.ct) or d == self.dont_build_wall:
                    continue
                building_entity = get_entity(check_pos, self.ct)
                if (building_entity in IGNORED_BUILDINGS or is_team_road(check_pos, self.ct)) and self.ct.get_tile_env(check_pos) != Environment.WALL:
                    if self.ct.can_destroy(check_pos):
                        self.ct.destroy(check_pos)
                    if self.ct.can_build_barrier(check_pos):
                        self.ct.build_barrier(check_pos)
                    return

        if reached_ore and can_build:
            self.set_target(self.base_position, BASE_DIST, BotState.GOING_BACK, TargetTypes.BASE)
            
        elif self.current_state == BotState.GOING_TO_TARGET and env == Environment.EMPTY:
            print("Reached here 1")
            if self.position.distance_squared(self.base_position) <= BASE_DIST:
                print("Reached here 2")
                if is_exposed(self.position, self.ct) and get_entity(self.position, self.ct) == EntityType.BRIDGE: # Duplicate code fix later
                    print("Reached here 3")
                    for d in DIRECTIONS:
                        check_pos = self.position.add(d)
                        if not checkable_position(check_pos, self.ct) or \
                            self.ct.get_tile_env(check_pos) != Environment.EMPTY or \
                            not (get_entity(check_pos, self.ct) in IGNORED_BUILDINGS or is_team_road(check_pos, self.ct)):
                            continue
                        elif self.ct.can_destroy(check_pos) and is_team_road(check_pos, self.ct):
                            self.ct.destroy(check_pos)
                        print("Reached here 4")
                        if self.ct.can_build_launcher(check_pos):
                            self.ct.build_launcher(check_pos)
                            self.launchers_built += 1
                            break

                if self.ct.can_destroy(self.position) and is_team_road(self.position, self.ct):
                    self.ct.destroy(self.position)

                building_entity = get_entity(self.position, self.ct)
                if building_entity in IGNORED_BUILDINGS:
                    bridge_target_pos_choices = get_positions_of_entities(self.position, self.ct, 9, EntityType.SPLITTER, self.ct.get_team())
                    bridge_target_pos = random.choice(bridge_target_pos_choices) if bridge_target_pos_choices else None
                    if bridge_target_pos and self.ct.can_build_bridge(self.position, bridge_target_pos):
                        self.ct.build_bridge(self.position, bridge_target_pos)
                
                if not is_exposed(self.position, self.ct) and building_entity in CONVEYORS and same_team:
                    self.set_wandering()
            else:
                self.set_target(self.base_position, BASE_DIST, BotState.GOING_BACK, TargetTypes.BASE)
        
        self.dont_build_wall = None
    
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
                lambda p: (self.enemy_base_pos is None) or self.base_position.distance_squared(p) <= 1.3 * self.enemy_base_pos.distance_squared(p), 
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
        self.just_bridged = False
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
        if self.ct.can_destroy(from_pos) and is_team_road(from_pos, self.ct):
            self.ct.destroy(from_pos)

        bridge_target_pos_choices = get_positions_of_entities(from_pos, self.ct, 9, EntityType.SPLITTER, self.ct.get_team())
        
        if bridge_target_pos_choices and self.ct.get_tile_env(from_pos) not in ORE_SITES:
            bridge_target_pos = random.choice(bridge_target_pos_choices)
            to_pos = bridge_target_pos
        elif from_pos.distance_squared(self.base_position) <= BASE_DIST and not bridge_target_pos_choices:
            return

        print(f"Building conveyor chain from {from_pos} to {to_pos}")
        if self.position.distance_squared(from_pos) > 1:
            print("Too far away!")
            self.set_target(from_pos, 0, BotState.GOING_TO_TARGET, TargetTypes.CONNECT_BRIDGE)
            return

        building_id = self.ct.get_tile_building_id(from_pos)
        building_type = self.ct.get_entity_type(building_id) if building_id else None
        same_team = building_id and self.ct.get_team(building_id) == self.ct.get_team()
        
        if same_team and building_type in CONVEYORS:
            print("Reached existing chain")

            p = self.ct.get_position()
            if not self.build_harvester(p) and not self.build_bot_thrower(p, to_pos):
                self.set_wandering()
            return

        if from_pos.distance_squared(to_pos) > 1 or get_skibidi_distance(to_pos, self.base_position) == 2:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)

                if get_entity(to_pos, self.ct) in CONVEYORS:
                    self.just_bridged = True
                
                if connect_next:
                    self.set_target(to_pos, 0, BotState.GOING_TO_TARGET, TargetTypes.CONNECT_BRIDGE)
        elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, from_pos.direction_to(to_pos)):
            bot_id = self.ct.get_tile_builder_bot_id(from_pos)
            if not bot_id:
                self.ct.build_conveyor(from_pos, from_pos.direction_to(to_pos))
    
    def build_harvester(self, position):
        potential_harvester_pos = None
        for d in CARDINAL_DIRECTIONS:
            check_pos = position.add(d)
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
        if self.ct.get_tile_env(position) != Environment.EMPTY or get_entity(position, self.ct) is None:
            return
        
        ret = False
        if is_exposed(self.previous_position, self.ct) or (is_exposed(position, self.ct) and get_entity(position, self.ct) == EntityType.BRIDGE): # Duplicate code fix later
            candidate_positions = []
            for d in CARDINAL_DIRECTIONS:
                check_pos = position.add(d)
                if not checkable_position(check_pos, self.ct) or \
                    check_pos == move_pos or \
                    self.ct.get_tile_env(check_pos) != Environment.EMPTY or \
                    self.ct.get_tile_builder_bot_id(check_pos) or \
                    (get_entity(check_pos, self.ct) not in IGNORED_BUILDINGS and not is_team_road(check_pos, self.ct)):
                    continue
                ret = True
                candidate_positions.append(check_pos)

            pos_to_build = min(candidate_positions, key=lambda p: self.previous_position.distance_squared(p)) if candidate_positions else None
            if pos_to_build:
                if self.ct.can_destroy(pos_to_build) and is_team_road(pos_to_build, self.ct):
                    self.ct.destroy(pos_to_build)
                if self.ct.can_build_launcher(pos_to_build):
                    self.ct.build_launcher(pos_to_build)
                    self.launchers_built += 1
        return ret