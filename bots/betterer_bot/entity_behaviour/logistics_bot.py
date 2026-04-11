from cambc import Controller, Environment, Position, EntityType
from utils.tile_info import TileData
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class LogisticsBot(Bot):
    def __init__(self, ct: Controller):
        self.harvester_count = 0
        self.titanium_harvester_count = 0
        
        self.adhd_severity = 2000 if ct.get_current_round() <= 10 else EXPLORE_TIMER
        self.explore_timer = self.adhd_severity
        self.axionite_ore_sites = set()
        self.pending_checks = set()
        self.to_repair = set()
        self.checked = set()
        self.absolute_inting_traitors = set()
        self.dont_harvest = set()
        self.to_guard = set()

        self.visiting_queue = set()
        self.visited = set()

        self.current_target_type = TargetTypes.WANDER
        self.target_black_list = set()

        self.dont_build = False

        self.harvester_pos = None
        self.turrets = set()

        super().__init__(ct)
    
    def update_map(self):
        self.pending_checks.clear()
        self.checked.clear()
        self.absolute_inting_traitors.clear()
        self.to_repair.clear()
        self.to_guard.clear()
        
        if random.random() > DEMENTIA_RATE and self.target_black_list:
            self.target_black_list.pop()
            
        super().update_map()
        
        unconnected = set(filter(lambda p: p not in self.target_black_list, self.pending_checks - self.checked))
        if (self.current_target_type == TargetTypes.ORE or self.current_target_type == TargetTypes.SENTINEL or self.current_state == BotState.WANDERING) and unconnected:
            self.visited_ore_sites.discard(self.current_target_position)
            self.set_wandering()

    def update_tile(self, tile: Position, tile_data: TileData):
        ### 1. find the target

        if tile_data.environment == Environment.ORE_TITANIUM:
            if tile not in self.ore_sites:
                print(f"Inserted ore {tile}")
                if self.current_target_type == TargetTypes.ORE and tile.distance_squared(self.position) < 0.5 * self.current_target_position.distance_squared(self.position):
                    self.visited_ore_sites.discard(self.current_target_position)
                    self.set_wandering()
                if self.current_state == BotState.WANDERING:
                    self.set_wandering()
            self.ore_sites.add(tile)
        elif tile_data.environment == Environment.ORE_AXIONITE:
            if tile not in self.axionite_ore_sites and self.harvester_count > 1:
                if self.current_target_type == TargetTypes.ORE and tile.distance_squared(self.position) < 0.5 * self.current_target_position.distance_squared(self.position):
                    self.visited_ore_sites.discard(self.current_target_position)
                    self.set_wandering()
                if self.current_state == BotState.WANDERING:
                    self.set_wandering()
            self.axionite_ore_sites.add(tile)

        if tile_data.building_type in CONVEYORS and tile_data.own_team:
            damaged = self.ct.get_hp(tile_data.building_id) < self.ct.get_max_hp(tile_data.building_id)

            self.visiting_queue.add(tile)
            if tile.distance_squared(self.position) <= 4:
                self.visited.add(tile)

            if damaged:
                self.to_repair.add(tile)
                if self.current_target_type != TargetTypes.REPAIR and self.current_state != TargetTypes.REMOVAL:
                    self.set_wandering()
            else:
                self.to_repair.discard(tile)
            if tile_data.building_type != EntityType.SPLITTER and (tile_data.bot_team != self.team or tile_data.bot_id == self.id):
                conveyor_target = get_conveyor_target(tile, self.ct)
                if conveyor_target and checkable_position(conveyor_target, self.ct):
                    if conveyor_target not in self.checked:
                        self.pending_checks.add(conveyor_target)
                    target_info = self.get_from_pos(conveyor_target)
                    if (
                        (target_info and target_info.building_type in TURRETS and not target_info.own_team) or
                        (target_info and target_info.building_type in CONVEYORS and get_conveyor_target(tile, self.ct) == tile) or
                        (target_info and target_info.environment == Environment.WALL)
                    ):
                        self.absolute_inting_traitors.add(tile)
                        if self.current_target_type != TargetTypes.REMOVAL:
                            self.set_wandering()
        
        if tile_data and tile_data.building_type == EntityType.HARVESTER and tile_data.own_team:
            can_build_sentinel = False
            if all([turret.target_distance_squared(tile) >= SENTINEL_RANGE / 2 for turret in self.turrets]): # Tweak number
                can_build_sentinel = True

            for d in CARDINAL_DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                check_info = self.get_from_pos(check_pos)
                if check_info and check_info.building_type in TURRETS and not check_info.own_team:
                    self.absolute_inting_traitors.add(tile)
                    self.dont_harvest.add(tile)
                    if self.current_target_type != TargetTypes.REMOVAL: # i want guancheng to edge me until i cry
                        self.set_wandering()
                
                if can_build_sentinel and check_info and (check_info.building_type in IGNORED_BUILDINGS or check_info.building_type == EntityType.ROAD or check_info.destroyable()):
                    self.to_guard.add(check_pos)
                    if self.current_target_type != TargetTypes.SENTINEL and self.current_target_type != TargetTypes.REMOVAL and self.current_target_type != TargetTypes.REPAIR and self.current_target_type != TargetTypes.CONNECT_BRIDGE:
                        self.set_wandering()
                    

        if tile_data and tile_data.building_type in TURRETS:
            self.turrets.add(tile)

        ### 2. is it valid or nah

        if tile_data and tile_data.building_type not in INVALID_CONTAINERS:
            print(f"Added {tile} to checked")
            self.pending_checks.discard(tile)
            self.checked.add(tile)
        else:
            print(f"Tile {tile} is not being added")

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
                case TargetTypes.REPAIR:
                    damaged = tile_data and tile_data.building_id and self.ct.get_hp(tile_data.building_id) < self.ct.get_max_hp(tile_data.building_id)
                    if not damaged:
                        print("Repair target not actually damaged")
                        self.set_wandering()
                case TargetTypes.SENTINEL:
                    guard_data = self.get_from_pos(self.current_target_position)
                    if guard_data is None or not(guard_data.building_type in IGNORED_BUILDINGS or guard_data.building_type == EntityType.ROAD or guard_data.destroyable()):
                        self.set_wandering()

    def move_to_pos(self):
        super().move_to_pos()
        if self.ct.get_position().distance_squared(self.current_target_position) <= 2 and self.current_target_type == TargetTypes.REMOVAL:
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
        
        if self.current_state == BotState.WANDERING or self.current_target_type != TargetTypes.BASE:
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
        if self.current_state == BotState.WANDERING or self.current_target_type == TargetTypes.BASE:
            return super().reached_target()
        self.position = self.ct.get_position()
        
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
                        (not adjacent_data.bot_id or adjacent_data.bot_id != self.id)
                    ):
                        print(f"Building barrier at {adjacent_pos}")
                        if self.ct.can_destroy(adjacent_pos):
                            self.ct.destroy(adjacent_pos)
                        if self.ct.can_build_barrier(adjacent_pos):
                            self.ct.build_barrier(adjacent_pos)
                        return
                
                can_build = self.ct.get_global_resources()[0] >= self.ct.get_harvester_cost()[0]
                if can_build:
                    self.set_target(self.base_position, BASE_DIST, BotState.GOING_TO_TARGET, TargetTypes.BASE)
                    self.dont_build = True
            case TargetTypes.CONNECT_BRIDGE:
                self.set_target(self.base_position, BASE_DIST, BotState.GOING_TO_TARGET, TargetTypes.BASE)
            case TargetTypes.REPAIR:
                pass
            case TargetTypes.REMOVAL:
                if self.ct.can_destroy(self.current_target_position):
                    self.ct.destroy(self.current_target_position)
                    if target_data.building_type == EntityType.HARVESTER and self.ct.can_build_barrier(self.current_target_position):
                        self.ct.build_barrier(self.current_target_position)
                    self.set_wandering()
                if not target_data.building_id or not (target_data.own_team and (target_data.building_type in CONVEYORS or target_data.building_type == EntityType.HARVESTER)):
                    # Already removed
                    self.set_wandering()
            case TargetTypes.SENTINEL:
                can_build = self.ct.get_global_resources()[0] < self.ct.get_sentinel_cost()[0] and self.ct.get_action_cooldown() == 0
                if can_build and (target_data.building_type == None or target_data.is_team_road() or target_data.destroyable()):
                    if self.position == self.current_target_position:
                        self.move_to_adjacent()
                    
                    if self.ct.can_destroy(self.current_target_position):
                        self.ct.destroy(self.current_target_position)
                    
                    facing = self.base_position.direction_to(self.harvester_pos)
                    if self.ct.can_build_sentinel(self.current_target_position, facing):
                        self.ct.build_sentinel(self.current_target_position.fac )
                
    def nearest_unexplored(self):
        print("Finding nearest unexplored")
        to_delete = self.absolute_inting_traitors - self.target_black_list # set(filter(lambda p: p not in self.target_black_list, self.absolute_inting_traitors))
        if to_delete:
            traitor = next(iter(to_delete))
            self.set_target(traitor, 0, BotState.GOING_TO_TARGET, TargetTypes.REMOVAL)
            print(f"Nearest unexplored is a traitor at: {traitor}")
            return traitor

        to_heal = self.to_repair - self.target_black_list # set(filter(lambda p: p not in self.target_black_list, self.to_repair))
        if to_heal:
            to_check = next(iter(to_heal))
            self.set_target(to_check, 2, BotState.GOING_TO_TARGET, TargetTypes.REPAIR)
            print(f"Nearest unexplored is a damaged building at: {to_check}")
            return to_check

        unconnected = set(filter(lambda p: p not in self.target_black_list and self.is_passable(p), self.pending_checks - self.checked))
        if unconnected:
            to_check = next(iter(unconnected))
            self.pending_checks.discard(to_check)
            self.set_target(to_check, 0, BotState.GOING_TO_TARGET, TargetTypes.CONNECT_BRIDGE)
            print(f"Nearest unexplored is an unconnected conveyor at: {to_check}")
            return to_check

        unguarded = self.to_guard - self.target_black_list # set(filter(lambda p: p not in self.target_black_list, self.to_guard))
        if unguarded:
            to_check = next(iter(unguarded))
            self.pending_checks.discard(to_check)
            self.set_target(to_check, 0, BotState.GOING_TO_TARGET, TargetTypes.SENTINEL)
            print(f"Nearest unexplored is a unprotected area at: {to_check}")
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
                ) and p not in self.target_black_list and p not in self.dont_harvest, 
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
            to_visit = self.visiting_queue - self.visited - self.target_black_list
            if to_visit:
                next_pos = next(iter(to_visit))
                self.set_target(next_pos, 4, BotState.WANDERING, TargetTypes.WANDER)
                print(f"Wandering to {next_pos} from visiting queue")
                return
            next_pos = super().nearest_unexplored()
            self.explore_timer -= 1
            if self.explore_timer <= 0:
                self.visited.clear()
                self.explore_timer = self.adhd_severity
            self.set_target(next_pos, 16, BotState.WANDERING)

    def set_target(self, target_pos, distance_squared, state, target_type=TargetTypes.WANDER):
        self.current_target_type = target_type
        return super().set_target(target_pos, distance_squared, state)
    
    def build_conveyor_chain(self, from_pos: Position, to_pos: Position):
        def get_closest_base_pos() -> Position:
            dx = from_pos.x - self.base_position.x
            dy = from_pos.y - self.base_position.y

            step_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
            step_y = 1 if dy > 0 else (-1 if dy < 0 else 0)

            return Position(self.base_position.x + step_x, self.base_position.y + step_y)
        print("Called build conveyor chain")
        from_data = self.get_from_pos(from_pos)
        if self.ct.can_destroy(from_pos) and (from_data.destroyable() or from_data.is_team_road()):
            self.ct.destroy(from_pos)

        bridge_target_pos_choices = self.get_positions_of_entities(from_pos, 9, EntityType.SPLITTER, self.team)
        p = self.ct.get_position()

        closest_base_pos = get_closest_base_pos()
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
        
        if not to_pos:
            print("No target pos for conveyor chain")
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
            if not from_data.bot_id or from_data.bot_team == self.team:
                self.ct.build_conveyor(from_pos, dir)
    
    def build_harvester(self, p=None):
        potential_harvester_pos = p or self.previous_position
        
        if not potential_harvester_pos or potential_harvester_pos not in self.visited_ore_sites or potential_harvester_pos in self.dont_harvest:
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