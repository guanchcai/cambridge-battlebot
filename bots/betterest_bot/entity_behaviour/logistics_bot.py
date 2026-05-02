from collections import deque

from cambc import Controller, Environment, Position, EntityType, ResourceType
from utils.tile_info import TileData
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class LogisticsBot(Bot):
    def __init__(self, ct: Controller):
        self.harvester_count = 0
        self.titanium_harvester_count = 0
        
        self.adhd_severity = 2000 if ct.get_current_round() <= 2 else EXPLORE_TIMER
        self.explore_timer = self.adhd_severity
        self.axionite_ore_sites = set()
        self.pending_checks = set()
        self.to_repair = set()
        self.checked = set()
        self.absolute_inting_traitors = set()
        self.dont_harvest = set()
        self.to_guard = set()
        self.enemy_intruder = set()

        self.previous_targets = deque(maxlen=7)
        self.previous_targets.append(None)

        self.visiting_queue = set()
        self.visited = set()

        self.current_target_type = TargetTypes.WANDER
        self.unreachable_targets = set()
        self.target_black_list = set()
        self.target_args = []

        self.dont_build = None

        self.turrets = set()

        super().__init__(ct)
    
    def update_map(self):
        self.pending_checks.clear()
        self.checked.clear()
        self.absolute_inting_traitors.clear()
        self.to_guard.clear()
        self.target_black_list.clear()
        self.enemy_intruder.clear()
        
        if random.random() > DEMENTIA_RATE and self.unreachable_targets:
            self.unreachable_targets.pop()
        
        print("Updating map")
        super().update_map()
        print("Updated map")
        print(f"Previous targets: {self.previous_targets}")
        self.target_black_list = self.unreachable_targets.union(filter(lambda x: self.previous_targets.count(x) >= 4, self.previous_targets))
        self.update_targets()

    def update_tile(self, tile: Position, tile_data: TileData):
        ### 1. find the target                
        if tile_data.environment == Environment.ORE_TITANIUM:
            self.ore_sites.add(tile)

        elif tile_data.environment == Environment.ORE_AXIONITE:
            self.axionite_ore_sites.add(tile)

        if tile_data.own_team and not tile_data.is_team_road():            
            damaged = self.ct.get_hp(tile_data.building_id) < self.ct.get_max_hp(tile_data.building_id)
            if damaged:
                self.to_repair.add(tile)

        if tile_data.building_type in CONVEYORS and tile_data.own_team:

            self.visiting_queue.add(tile)

            if tile.distance_squared(self.position) <= 4:
                self.visited.add(tile)
                
            conveyor_target = get_conveyor_target(tile, self.ct)
            if conveyor_target and checkable_position(conveyor_target, self.ct):
                if tile_data.bot_id == self.id or tile_data.bot_id is None:
                    self.pending_checks.add((conveyor_target, tile))
                target_info = self.get_from_pos(conveyor_target)
                if target_info and (
                    (target_info.building_type not in INVALID_CONTAINERS and not target_info.own_team) or
                    (target_info.building_type in CONVEYORS and not target_info.own_team) or
                    (target_info.environment == Environment.WALL) or 
                    (conveyor_target in self.target_black_list)
                    # (target_info.bot_id and not target_info.bot_team and target_info.building_type in INVALID_CONTAINERS)
                ):
                    self.absolute_inting_traitors.add(tile)
                if target_info and (
                    (target_info.bot_id and not target_info.bot_team and target_info.building_type in INVALID_CONTAINERS)
                ):
                    self.enemy_intruder.add(conveyor_target)
        
        if tile_data and tile_data.building_type == EntityType.HARVESTER and tile_data.own_team:
            can_build_turrets = not self.turrets or sum(turret.distance_squared(tile) <= 1 for turret in self.turrets) < 2

            can_guard = set()
            has_conveyor = False
            potential_conveyor_pos = set()
            nearby_bot = False
            for d in CARDINAL_DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    print(f"Can't check {check_pos}")
                    if is_in_bound(check_pos, self.ct):
                        has_conveyor = True
                    continue
                
                check_id = self.ct.get_tile_building_id(check_pos)
                check_building = self.ct.get_entity_type(check_id) if check_id else None
                check_team = self.ct.get_team(check_id) if check_id else None
                check_environment = self.ct.get_tile_env(check_pos)
                check_bot = self.ct.get_tile_builder_bot_id(check_pos)

                # if check_building in TURRETS and check_team != self.team:
                #     self.absolute_inting_traitors.add(tile)
                
                if (check_building in CAN_BUILD_OVER or (check_team == self.team and check_building == EntityType.BARRIER)) and \
                    check_environment != Environment.WALL:
                    if check_bot is None or check_bot == self.id:
                        can_guard.add(check_pos)
                    potential_conveyor_pos.add((check_pos, tile))
                
                if check_bot and self.ct.get_team(check_bot) != self.team:
                    self.enemy_intruder.add(check_pos)

                if check_building in CONVEYORS:
                    has_conveyor = True
            
            for d in DIRECTIONS:
                check_pos = tile.add(d)
                if not is_in_bound(check_pos, self.ct):
                    print(f"Can't check {check_pos}")
                    continue
                check_info = self.get_from_pos(check_pos)
                if not check_info:
                    continue
                if check_info and check_info.bot_id and check_info.bot_id != self.id and check_info.bot_team:
                    nearby_bot = True
            
            if not has_conveyor:
                self.pending_checks = self.pending_checks.union(potential_conveyor_pos)
            
            print(f"Positions to guard: {can_guard}")
            print(f"Nearby: {nearby_bot} and {can_guard} and {can_build_turrets}")
            if not nearby_bot and can_guard:
                if tile_data.environment == Environment.ORE_TITANIUM and can_build_turrets:
                    self.to_guard.update(can_guard)
            
            self.visited_ore_sites.add(tile)

        if tile_data and tile_data.own_team and tile_data.building_type in TURRETS:
            self.turrets.add(tile)
        elif tile in self.turrets:
            self.turrets.discard(tile)

        ### 2. is it valid or nah
        if tile in self.visiting_queue and tile_data.building_type not in CONVEYORS:
            self.visiting_queue.discard(tile)

        if tile_data and tile_data.building_type not in INVALID_CONTAINERS:
            self.checked.add(tile)
        else:
            pass

        if (
            self.current_state == BotState.GOING_TO_TARGET and
            self.current_target_position == tile and tile_data.bot_id != self.id
        ):
            if not self.is_valid_target():
                self.set_target(self.base_position, 16, BotState.WANDERING)

    def move_to_pos(self):
        super().move_to_pos()
        if self.ct.get_position().distance_squared(self.current_target_position) <= 2 and \
            (
                # self.current_target_type == TargetTypes.REMOVAL or \
                self.current_target_type == TargetTypes.SENTINEL or \
                self.current_target_type in BUILDING_CONVEYORS
            ):
            self.reached_target()

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
        
        if self.current_state == BotState.WANDERING or self.current_target_type not in BUILDING_CONVEYORS:
            print("Just building road normally")
            print(f"Current state is: {self.current_state}, and target type is: {self.current_target_type}")
            return super().build_road(move_pos, next_pos)
        
        enemy_team = tile_data and not tile_data.own_team

        if self.ct.can_fire(self.position) and enemy_team:
            self.ct.fire(self.position)

            # This checks if the building is still alive
            if self.ct.get_tile_building_id(self.position):
                return False
        
        new_building_id = self.ct.get_tile_building_id(self.position)
        
        if (self.position != self.dont_build) and (new_building_id is None or tile_data.is_team_road()):
            self.build_conveyor_chain(self.position, move_pos)
            return False
        else:            
            self.build_conveyor_chain(move_pos, next_pos)

            
        return True
    
    def unreachable_path(self):
        if self.current_state == BotState.GOING_TO_TARGET:
            self.unreachable_targets.add(self.current_target_position)
        return super().unreachable_path()
    
    def run_flood_fill(self):
        if self.current_target_type in BUILDING_CONVEYORS:
            self.pathfind_status, self.distance_map = self.path_finder.run(
                self.position,
                self.current_target_position,
                self.target_distance_squared,
                self.ct,
                True
            )
        else:
            self.pathfind_status, self.distance_map = self.path_finder.run(
                self.position,
                self.current_target_position,
                self.target_distance_squared,
                self.ct,
                False
            )
    
    def reached_target(self):
        print(f"Reached target timer {self.ct.get_cpu_time_elapsed()}, current target type {self.current_target_type}")
        if self.current_state == BotState.WANDERING or self.current_target_type in BUILDING_CONVEYORS:
            return super().reached_target()
        
        if not self.is_valid_target():
            self.set_target(self.base_position, 16, BotState.WANDERING)
            return
        self.position = self.ct.get_position()
        
        target_data = self.get_from_pos(self.current_target_position)
        same_team = target_data and target_data.own_team

        if not same_team:
            if self.ct.can_fire(self.current_target_position):
                self.ct.fire(self.current_target_position)

        match self.current_target_type:
            case TargetTypes.ORE:
                if self.position != self.current_target_position:
                    return
                for d in CARDINAL_DIRECTIONS:
                    adjacent_pos = self.position.add(d)
                    if not checkable_position(adjacent_pos, self.ct):
                        continue
                    adjacent_data = self.get_from_pos(adjacent_pos)
                    if (
                        adjacent_data and 
                        adjacent_data.environment != Environment.WALL and 
                        (get_entity(adjacent_pos, self.ct) in IGNORED_BUILDINGS or adjacent_data.is_team_road()) and
                        not adjacent_data.bot_id
                    ):
                        print(f"Building barrier at {adjacent_pos}")
                        if self.ct.can_destroy(adjacent_pos) and get_entity(adjacent_pos, self.ct) == EntityType.ROAD:
                            self.ct.destroy(adjacent_pos)
                        if self.ct.can_build_barrier(adjacent_pos):
                            self.ct.build_barrier(adjacent_pos)
                        return
                
                can_build = self.ct.get_global_resources()[0] >= self.ct.get_harvester_cost()[0]
                if can_build:
                    self.visited_ore_sites.add(self.current_target_position)
                    print(f"Added ore site {self.current_target_position} to visited")
                    self.dont_build = self.current_target_position # Worry about it later
                    if target_data.environment == Environment.ORE_AXIONITE:
                        self.set_target(self.base_position, BASE_DIST, BotState.GOING_TO_TARGET, TargetTypes.CARRYING_AXIOMNITE, ResourceType.RAW_AXIONITE)
                    else:
                        self.set_target(self.base_position, BASE_DIST, BotState.GOING_TO_TARGET, TargetTypes.BASE, ResourceType.TITANIUM)
            case TargetTypes.CONNECT_BRIDGE:
                from_conveyor = self.target_args[0]
                print(f"Disconnected conveyor: {from_conveyor}")
                from_conveyor_data = self.get_from_pos(from_conveyor)
                if not from_conveyor_data.own_team or from_conveyor_data.building_type not in CONVEYORS:
                    if from_conveyor_data.building_type == EntityType.HARVESTER:
                        if from_conveyor_data.environment == Environment.ORE_AXIONITE:
                            self.set_target(self.base_position, BASE_DIST, BotState.GOING_TO_TARGET, TargetTypes.CARRYING_AXIOMNITE)
                        else:
                            self.set_target(self.base_position, BASE_DIST, BotState.GOING_TO_TARGET, TargetTypes.BASE)

                    return
                
                resource = self.ct.get_stored_resource(from_conveyor_data.building_id)
                if resource == ResourceType.RAW_AXIONITE:
                    self.set_target(self.base_position, BASE_DIST, BotState.GOING_TO_TARGET, TargetTypes.CARRYING_AXIOMNITE)
                else:
                    self.set_target(self.base_position, BASE_DIST, BotState.GOING_TO_TARGET, TargetTypes.BASE)
            case TargetTypes.REPAIR:
                if not self.is_valid_target():
                    self.to_repair.discard(self.current_target_position)
                    self.set_target(self.base_position, 16, BotState.WANDERING)

            case TargetTypes.REMOVAL:
                if self.ct.can_destroy(self.current_target_position) and target_data.building_type == self.target_args[0]:
                    self.ct.destroy(self.current_target_position)
                if self.ct.can_build_road(self.current_target_position):
                    self.ct.build_road(self.current_target_position)
            case TargetTypes.SENTINEL:
                can_build = self.ct.get_global_resources()[0] >= self.ct.get_gunner_cost()[0] and self.ct.get_action_cooldown() == 0
            
                if can_build and (target_data.building_type == None or target_data.is_team_road() or target_data.destroyable()):
                    if self.position == self.current_target_position:
                        self.move_to_adjacent()
                    
                    if self.ct.can_destroy(self.current_target_position) and (target_data.destroyable() or target_data.is_team_road()) and self.ct.get_position() != self.current_target_position:
                        self.ct.destroy(self.current_target_position)
                    facing = random.choice(list(DIAGONAL_DIRECTIONS))
                    
                    print(f"Can build sent: {self.ct.can_build_gunner(self.current_target_position, facing)}")
                    if not self.ct.can_build_gunner(self.current_target_position, facing):
                        print(f"Reason: {get_entity(self.current_target_position, self.ct)}")
                    if self.ct.can_build_gunner(self.current_target_position, facing):
                        self.ct.build_gunner(self.current_target_position, facing)
            case TargetTypes.INTRUDER:
                if self.ct.can_fire(self.position) and not self.get_from_pos(self.position).own_team:
                    self.ct.fire(self.position)
                if self.ct.get_action_cooldown() == 0 and self.ct.get_global_resources() >= self.ct.get_launcher_cost():
                    for d in DIRECTIONS:
                        check_pos = self.current_target_position.add(d)
                        if not checkable_position(check_pos, self.ct):
                            continue
                        if check_pos.distance_squared(self.position) > 2:
                            continue
                        check_info = self.get_from_pos(check_pos)
                        if self.ct.can_destroy(check_pos) and check_info.building_type in CAN_BUILD_OVER:
                            self.ct.destroy(check_pos)
                            if check_pos == self.position:
                                self.move_to_adjacent()
                        if self.ct.can_build_launcher(check_pos):
                            self.ct.build_launcher(check_pos)
                            
                            self.set_target(self.base_position, 16, BotState.WANDERING)
                            break

    def nearest_unexplored(self):
        def has_adjacent_ally(tile):
            for d in DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                t_d = self.get_from_pos(check_pos)
                if t_d and t_d.is_team_bot(self.id):
                    return True
            return False
        def has_adjacent_launcher(tile):
            for d in DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                t_d = self.get_from_pos(check_pos)
                if t_d and t_d.own_team and t_d.building_type == EntityType.LAUNCHER:
                    return True
            return False
        
        print("Finding nearest unexplored")
        to_delete = self.absolute_inting_traitors - self.target_black_list # set(filter(lambda p: p not in self.target_black_list, self.absolute_inting_traitors))
        if to_delete:
            traitor = next(iter(to_delete))
            self.set_target(traitor, 0, BotState.GOING_TO_TARGET, TargetTypes.REMOVAL, self.ct.get_entity_type(self.ct.get_tile_building_id(traitor)))
            print(f"Nearest unexplored is a traitor at: {traitor}")
            return traitor

        to_heal = {
            tile for tile in self.to_repair - self.target_black_list
            if not has_adjacent_ally(tile)
        }
        print(f"Damaged tiles: {self.to_repair}")
        if to_heal:
            to_check = min(to_heal, key=lambda x: self.position.distance_squared(x))
            self.set_target(to_check, 2, BotState.GOING_TO_TARGET, TargetTypes.REPAIR)
            print(f"Nearest unexplored is a damaged building at: {to_check}")
            return to_check
        
        to_deport = {
            tile for tile in self.enemy_intruder - self.target_black_list
            if not has_adjacent_launcher(tile) and not has_adjacent_ally(tile)
        }
        if to_deport:
            le_mexican = min(to_deport, key=lambda x: self.position.distance_squared(x))
            self.set_target(le_mexican, 2, BotState.GOING_TO_TARGET, TargetTypes.INTRUDER)
            print(f"Nearest unexplored is a intruder to be taken care of at: {le_mexican}")
            return le_mexican

        if self.current_target_type in BUILDING_CONVEYORS:
            # Stay on target
            return True

        unconnected = set(filter(lambda p: p[0] not in self.checked and p[0] not in self.target_black_list and self.is_passable(p[0]), self.pending_checks))
        if unconnected:
            to_check = next(iter(unconnected))
            self.set_target(to_check[0], 0, BotState.GOING_TO_TARGET, TargetTypes.CONNECT_BRIDGE, to_check[1])
            print(f"Nearest unexplored is an unconnected conveyor at: {to_check[0]}")
            return to_check
        
        if self.current_target_type == TargetTypes.CONNECT_BRIDGE:
            return True

        unguarded = self.to_guard - self.target_black_list # set(filter(lambda p: p not in self.target_black_list, self.to_guard))
        if unguarded:
            to_check = next(iter(unguarded))
            self.set_target(to_check, 0, BotState.GOING_TO_TARGET, TargetTypes.SENTINEL)
            print(f"Nearest unexplored is a unprotected area at: {to_check}")
            return to_check

        if (self.adhd_severity == EXPLORE_TIMER or self.ct.get_global_resources()[0] < self.ct.get_harvester_cost()[0]) and (self.current_target_type == TargetTypes.WANDER or self.current_target_type == TargetTypes.ORE):
            print("i found an ore blegh :)")
            if self.current_target_type == TargetTypes.ORE:
                if self.position == self.current_target_position:
                    return self.current_target_position
                self.visited_ore_sites.discard(self.current_target_position)
            return False

        unvisited_ores = None

        if self.harvester_count <= 1 or self.titanium_harvester_count <= 0.75 * self.harvester_count or self.ct.get_current_round() <= 100:
            unvisited_ores = self.ore_sites - self.visited_ore_sites
        else:
            unvisited_ores = self.ore_sites.union(self.axionite_ore_sites) - self.visited_ore_sites
        print(f"Unvisited: {unvisited_ores}")
        unvisited_ores = set(
            filter(
                lambda p: (
                    (self.enemy_base_pos is None) or self.base_position.distance_squared(p) <= (min(0.5 + self.ct.get_current_round() / 1500 * 0.5, 1) * max(self.map_width, self.map_height)) ** 2
                ) and not (
                    checkable_position(p, self.ct) and self.ct.get_tile_builder_bot_id(p) is not None and self.ct.get_tile_builder_bot_id(p) != self.id
                ) and p not in self.target_black_list and p not in self.dont_harvest, 
                unvisited_ores
            )
        )
        
        if unvisited_ores:
            to_visit = min(unvisited_ores, key=lambda ore: self.position.distance_squared(ore))
            self.set_target(to_visit, 0, BotState.GOING_TO_TARGET, TargetTypes.ORE)

            print(f"Nearest unexplored ore is at: {to_visit}")
            return to_visit
        
        return self.current_target_position if self.current_state == BotState.GOING_TO_TARGET and self.is_valid_target() else None
    
    def update_targets(self):
        def visit_conveyors():
            to_visit = self.visiting_queue - self.visited - self.target_black_list
            if to_visit:
                next_pos = min(to_visit, key=lambda p: self.position.distance_squared(p))
                self.set_target(next_pos, 4, BotState.WANDERING, TargetTypes.WANDER)
                print(f"Wandering to {next_pos} from visiting queue")
            return to_visit

        print("Setting wandering")
        
        prev_pos = self.current_target_position
        next_pos = self.nearest_unexplored()
        if next_pos and self.current_target_type != TargetTypes.ORE:
            self.visited_ore_sites.discard(prev_pos)
        if next_pos:
            self.visited.clear()
            return
        elif (self.current_target_type == TargetTypes.ORE or self.current_state == BotState.WANDERING) and self.ct.get_global_resources()[0] < self.ct.get_harvester_cost()[0]:
            if not visit_conveyors():
                self.visited.clear()
        else:
            self.explore_timer -= 1
            if self.explore_timer > 0:
                next_pos = super().nearest_unexplored()
                self.set_target(next_pos, 16, BotState.WANDERING)
                return
            elif self.explore_timer == 0:
                self.visited.clear()

            if not visit_conveyors():
                self.explore_timer = self.adhd_severity
                

    def set_target(self, target_pos, distance_squared, state, target_type=TargetTypes.WANDER, *args):
        self.current_target_type = target_type
        self.target_args = args
        if target_pos != self.previous_targets[-1] and target_pos != self.base_position and target_type != TargetTypes.WANDER:
            self.previous_targets.append(target_pos)
        return super().set_target(target_pos, distance_squared, state)
    
    def build_conveyor_chain(self, from_pos: Position, to_pos: Position):
        if not from_pos or not to_pos:
            return
        
        print("Called build conveyor chain")
        from_data = self.get_from_pos(from_pos)
        if self.ct.can_destroy(from_pos) and (from_data.destroyable() or from_data.is_team_road()):
            self.ct.destroy(from_pos)

        print(f"Building conveyor chain from {from_pos} to {to_pos}")
        
        same_team = from_data and from_data.own_team
        
        if same_team and from_data.building_type in CONVEYORS:
            print("Reached existing chain")

            if not self.build_harvester():
                self.set_target(self.base_position, 16, BotState.WANDERING)
            return
        
        dir = from_pos.direction_to(to_pos)
        if from_pos.distance_squared(to_pos) > 1:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)
                
                self.set_target(to_pos, 0, BotState.GOING_TO_TARGET, TargetTypes.CONNECT_BRIDGE, from_pos)
        elif from_pos.distance_squared(to_pos) == 1 and self.ct.can_build_conveyor(from_pos, dir):
            self.ct.build_conveyor(from_pos, dir)
    
    def build_harvester(self, p=None):
        potential_harvester_pos = p or self.previous_position
        print(f"Trying to build harvester {potential_harvester_pos}")
        if not potential_harvester_pos or not checkable_position(potential_harvester_pos, self.ct) or potential_harvester_pos in self.dont_harvest:
            print("Early return 1")
            return
        if potential_harvester_pos == self.ct.get_position():
            print("Early return 2")
            return
        tile_data = self.get_from_pos(potential_harvester_pos)

        building_id = self.ct.get_tile_building_id(potential_harvester_pos)
        
        etype = self.ct.get_entity_type(building_id) if building_id else None

        if (
            tile_data and 
            tile_data.environment in ORE_SITES and 
            (etype in IGNORED_BUILDINGS or (etype in CAN_BUILD_OVER and self.ct.get_team(building_id) == self.team)) 
            and potential_harvester_pos in self.visited_ore_sites
        ):
            print("Reached here")
            print(self.ct.can_build_harvester(potential_harvester_pos))
            print(potential_harvester_pos)
            if self.ct.can_destroy(potential_harvester_pos) and get_entity(potential_harvester_pos, self.ct) in CAN_BUILD_OVER:
                self.ct.destroy(potential_harvester_pos)
            if self.ct.can_build_harvester(potential_harvester_pos):
                self.ct.build_harvester(potential_harvester_pos)
                self.harvester_count += 1
                if tile_data.environment == Environment.ORE_TITANIUM:
                    self.titanium_harvester_count += 1
            return True
        
    def handle_thrown(self):
        self.set_target(self.base_position, 16, BotState.WANDERING)
        self.visited_ore_sites.discard(self.current_target_position)
        return super().handle_thrown()
    
    def is_valid_target(self):
        tile = self.current_target_position
        tile_data = self.get_from_pos(tile)
        if tile in self.target_black_list:
            return False
        if not checkable_position(tile, self.ct):
            return True
        match self.current_target_type:
            case TargetTypes.ORE:
                if (
                    not self.is_passable(tile) or \
                    (tile_data.own_team and tile_data.building_type in CONVEYORS) or \
                    not any([self.is_passable(tile.add(d)) for d in CARDINAL_DIRECTIONS])
                ):
                    print("Ore target not actually reachable")
                    self.dont_harvest.add(tile)
                    return False
            case TargetTypes.CONNECT_BRIDGE:
                if (not self.is_passable(tile)):
                    return False
                if (tile_data.bot_team):
                    return False
            case TargetTypes.REPAIR:
                damaged = tile_data and tile_data.building_id and self.ct.get_hp(tile_data.building_id) < self.ct.get_max_hp(tile_data.building_id)
                if not damaged:
                    print("Repair target not actually damaged")
                    self.to_repair.discard(tile)
                    return False
            case TargetTypes.SENTINEL:
                guard_data = self.get_from_pos(self.current_target_position)
                if guard_data is None or not (guard_data.building_type in IGNORED_BUILDINGS or guard_data.building_type == EntityType.ROAD or guard_data.destroyable()) or (guard_data.bot_team and guard_data.bot_id != self.id):
                    self.to_guard.discard(tile)
                    return False
                elif any([turret.distance_squared(tile) < 2 for turret in self.turrets]):
                    self.to_guard.discard(tile)
                    return False
            case TargetTypes.WANDER:
                target_data = self.get_from_pos(self.current_target_position)
                if target_data and not (target_data.own_team and target_data.building_type in CONVEYORS):
                    self.visiting_queue.discard(self.current_target_position)
            case TargetTypes.INTRUDER:
                target_data = self.get_from_pos(self.current_target_position)
                if target_data and (target_data.bot_team is None or target_data.bot_team) and target_data.building_type not in INVALID_CONTAINERS:
                    self.enemy_intruder.discard(self.current_target_position)
                    return False
                if self.check_for_entity(self.current_target_position, DIRECTIONS, EntityType.LAUNCHER, self.team):
                    self.enemy_intruder.discard(self.current_target_position)
                    return False
        return True

    def encountered_wall(self, wall_pos: Position):
        if wall_pos.distance_squared(self.position) > 1:
            self.set_target(self.base_position, 16, BotState.WANDERING)
            return
        
        wall_info = self.get_from_pos(wall_pos)
        if not wall_info:
            return
        
        if self.current_target_type in BUILDING_CONVEYORS:
            if wall_info.is_team_bot(self.id):
                self.set_target(self.base_position, 16, BotState.WANDERING)
            else:
                # if self.ct.can_destroy(self.position):
                #     self.ct.destroy(self.position)
                #     if self.ct.can_build_road(self.position):
                #         self.ct.build_road(self.position)
                #     self.checked.discard(self.position)
                    
                self.set_target(self.base_position, 16, BotState.WANDERING)
            
"""
##############*****=====---:::::...                                                                .-+######################################
#############******=====--:::::...                           ..:-=+++-:.                            .:-+####################################
############******=====--:::::..                         .:-+*********+++-:.                       ...:--*##################################
##########******+=====---::::...                   ...:=****************+**+-.                    ....----+#################################
***************======---:::::....           ....-=**##*******************++***=:                 .*####**+=*################################
===***********+=======-=-:::::::::::::---=+***#**#*************************++***+:                .=*#######################################
========+**+=================-===++****######*******************************+++***=.               .:+######################################
---=====================+**###############***********************************+++****:               .:+#####################################
::::--======++++*+++=++*###############****************************++=---:::::::.:..::               .:+####################################
::::::-====****#**++++**############****************+********+===+++*++==-:::...                      .-*###################################
...:::-==+*#####**++**##############***************++*****+==+******+===-::                            .=###################################
  ..::==*#####******#################****#*********+***+==+****++=--:.                                 .:+##################################
   .:-+*#######**################**#*##*******+****+*=-=*####***+==---.                                ..=##################################
   :-*###########################********+****+***++--=*###***+==:--:.                                 ..-*#################################
  .-*##########################*###*******++*****++-:-==--::.                                    --.  ...-*#################################
 .:*###****##########*************+++******++*****+-.=+====-.                               .    +#*=:..:-*#################################
 -************#*******##############**=--=*+++*****=.:=+=-:                               ....   +####=-:-*#################################
.=**************#############*+=-:::::.:.  :=+*+****=..---:                           :==:.::..  -#####*-*##################################
-**********+*###############*+=-:..        .-+**+*+**=.  ..                     . .-+*+*+--..-.. :*#########################################
-*******+=+*###########*+-:::               .:-++++*+-:.::..        .......::--=++++****+-:.....   :+#######################################
**+==+**+=-----::::..                    :+++++**+=-+*++++**+++*++++++**++**********+=-:::..    .+***#######################################
**--+**=:..                            :-********++=--++**++**********************+-:...  .      .-*########################################
*+-:=+-.                              .=*****+*+++++*=:...:--=++++************+=-:.....            :+#######################################
  -+**+:.:-.                        .. ..:=****++++++**####*=. .+****++=-===+++++=-:...                 .=*#################################
  .=***+-..                           :-+******+*++**####**-      :=**####*****=-:.                      .=*################################
   .+****+=:....                  .:-+********+++*####**=:.         .-*##*##*******++-.                  .:+################################
    :+*******+=------:::::::-----+**********+++***#**+-.             -***************+:                    -*###############################
     :****************************+*******+++*#*===-.                -***************=.                    :*###############################
     .-**************************+*******++*##*=:::.                 -***********++++:                      =###############################
      .=*************************+*****++*#####*+-:.                  -+*+=::.                            ..=###############################
.-*=.  .=***************************++++*########**+=-:                                                    .=*##############################
=+##+-..:=***********************+++++**##############**+-.                                                .-*##############################
#*--*##+-:=******************+++++**++*###############**+=.           .-+*--=:                             .=###############################
*:-######=:=***************++*****+++**##############*+:.        ...=*####*=#*.                            .+###############################
-.....:+**=-=************+*###++*++++**############**-:.    .-+*###*-=#####*###- +*                        .-*##############################
-.+-..==:=*+--********++*###**++*++++**###########*+-. .-+*=+########*#####*=*#*-                           .=##############################
*--- -=::..=-:-+******++*##******+++***##########*=-...=####*-*##**###=##*=:                                 -*#############################
#+:-**:.-----=::+*******+********+++***#########*+:. =*+:+#*+-*###=**=::-:.                                  :*#############################
##+-**.-++++=++::=*******+++*****+****##########*-. ..:*#::=#+=#*--+#**-.                                    .=#############################
###+-:.:++++==**=-=********+=+***++***##########+:.  -+::**=#+=*##**=.            ..                          :+############################
####+-..-+++=::+*+--+*******++=+*****###########+:.   ..:**=*###**=.      ..:-+***********=-:                  -*###########################
#####*:.::===:-+***--+*******++==+****##########*=.. .=*-+*####*--..  ..-=**##########*****+:                  .-*##########################
#######+:-=:::-*####=-=******++++=+++*###########*==--=*#####*+---::-+*##############*****+:                    .=##########################
#########+-====-*####*-=*****++++++=-*######################*+==+**##################*****-                      .*#########################
############*+=--=****=--+****+++***++*####################****###################*******=                       .:*########################
########################*==***+++***++++*#####################################**********-                          -*#######################
##########################+=+***+++**+***+*############################***************=.                            +#######################
###########################*=-+*+++++++****+**#######################***************+.                              :*######################
#############################*=-=+++++=++++++++**#####************++++=--::::::-==-.                                 -*#####################
###############################+---:::.:=++++++=::=====-------::.....                                                 -*####################
################################*==*++======----...........                                                             :-+*################
#################################*=+*********++++++***+++==--::.                                                         ..-*###############
###################################++*******+++***********++++++===-=-----:::......                 ....                   .+*##############
####################################*+*********+++********==************+++=====-:...         :++****++=--.                   .:-++*########
#####################################*++**********+********+=**+*****************+-....      .+*********-.                           .::-=::
######################################*++**********+*********-++=-+***************=-....     -*********+-                                   
#################################+=**#**+=+********+++********+++++=-=************=-.....   .+*********=.                                   
################***************+=+******++-+********++**************+--=**********=-......  :+*********:                                    
##############**+*++++++*****++++++**+*+==*+=+*****++++**************+--=*********=-......  :*********=.                              ...   
##############*+=-=+**+==****++++++++=--=***+-+****++++++*+******+-****=--==+*****=:.  .....-*********-.                          :=++=:    
##############*-+-+***++--++**+++++=-=+-+****=--+****+++++++******+-+****+=:......      ... -********+.                          =+***-     
##############*+++***++*-:--+*+++++-++=+**++*+-:-=+**+++++++*******+-=*****++=----:.  ......=********-.                         :+***-.     
##############*+=+**++***-::-=++*++=++-***+***+:::-++*++++++++*******=-+****+++=----:......:+*******+:                         .++**=:      
##############*+=+*******+-:-:-+++++=+=***++***=:--:-++++++++++*******+-=*****++=--------:.-********+..                        -++*=-       
##############*+++***+****=::+=-=+**++=***+*****::-+=-=++++++++*********==+****++=-------:.+********=..                        ++++:        
##############**++**++****-::-++=-+**++***+****+:::-*+=-+*+++++***********==***++=-------::*********-..              .-.      .=+=-         
##############**+++*++***+-=-:-+*+=+**++*+++***==+-:=+++=+***++************+-+*+++-------.:*********-..           .=++=:      :-=-:         
##############*+++*++++**++**+==+++++*++*++++**=+**+-+*+*+=*****************+==++++------.-*********-..          :+**+=:     .-=--.         
##############**+++*+++***+****==***++*++*+++**=+***+-+****++*****************+=-+++=----.-*********--.... .  .::*****-.   ...==--        :-
############################+:..:+****+*+*+++**+***++*==*++*********************++*++=---:=*********=-...:==---:+*****-.   -::==-.      .-: 
##########################*=.    .+**++***+**+*****++***+++++***********************++=--:+**********--=+*****--******-.. .-==++-.   .---.  
#########################*-.      -**********++****+*****+*+++***********************+=--+***********+********-+******+-..-+****-..:---:    
########################*-.        =**********+****+******+*+************************=++++********************+********=--+******+=-..      
#######################*-.         .***********+***+******+*************************+*++*******************************************-:      .
######################*=.           -************++*******************************+********++++***********************************=:    :-: 
######################+.            .=****************++++************************+*****++++++**+********************************=.   :===-:
#####################*-              :*********************++++**+**+**************+***++******+++*****************************+-.   :---:  
"""