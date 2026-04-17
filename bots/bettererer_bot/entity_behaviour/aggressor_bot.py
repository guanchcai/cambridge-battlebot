from utils.tile_info import TileData
from entity_behaviour.bot import Bot
from utils.constants import *
from utils.constants import _SENTINEL
from utils.helper_functions import *
from cambc import Controller, Position, Direction, EntityType, Environment, ResourceType
import random

class Aggressor(Bot):
    def __init__(self, ct: Controller):
        self.harvester_targets = []
        self.conveyor_targets = []
        self.turrets_in_range = []

        self.own_launcher_pos = None
        self.enemy_launchers = set()
        self.allied_launchers = set()
        self.rounds_without_launch = 0
        self.conveyor_ends = {}
        self.listening = False
        self.target_black_list = set()

        self.enemy_bots = set()

        self.to_eval = set()

        self.current_target_type = TargetTypes.WANDER
        self.current_target_source = None
        super().__init__(ct)

    # def move_to_pos(self):
    #     position = self.ct.get_position()
    #     super().move_to_pos()

    def update_map(self):
        self.aggression_targets = []
        self.turrets_in_range = []
        self.harvester_targets = []
        self.conveyor_targets = []
        self.allied_launchers.clear()
        self.enemy_bots.clear()
        self.conveyor_ends = {}
        self.to_eval.clear()
        if random.random() > DEMENTIA_RATE and self.target_black_list:
            self.target_black_list.pop()
        if random.random() > DEMENTIA_RATE and self.visited_ore_sites:
            self.visited_ore_sites.pop()
        super().update_map()

        print(self.to_eval)
        for tile in self.to_eval:
            tile_data = self.get_from_pos(tile)
            self.evaluate_aggressor_target(tile, tile_data)

        self.set_wandering()

    def update_tile(self, tile: Position, tile_data: TileData):
        if tile_data is None:
            return
        
        # if self.current_state == BotState.GOING_TO_TARGET and tile == self.current_target_position:
        #     if tile_data.bot_id and tile_data.bot_id != self.id:
        #         self.set_wandering()

        #     if tile_data.building_type not in PASSABLE:
        #         if not (tile_data.building_type == EntityType.LAUNCHER and tile_data.own_team):
        #             self.set_wandering()

        #     if tile_data.building_type in CONVEYORS:
        #         for ending in self.get_ends(tile):
        #             if ending and ending[0] in TURRETS and ending[1] == self.team:
        #                 self.set_wandering()
        
        enemy_team = tile_data.building_id and not tile_data.own_team

        if enemy_team and tile not in self.target_black_list: 
            self.to_eval.add(tile)
        elif tile_data.building_type == EntityType.LAUNCHER:
            self.allied_launchers.add(tile)

        if tile_data.bot_id and tile_data.bot_team != self.team:
            self.enemy_bots.add(tile)
        
    def unreachable_path(self):
        if self.current_state == BotState.WANDERING:
            return super().unreachable_path()
        
        self.target_black_list.add(self.current_target_position)
        self.set_wandering()
        # Check if we already have a launcher built
        # if self.own_launcher_pos is not None:
        #     own_launcher_data = self.get_from_pos(self.own_launcher_pos)

        #     own_launcher_exists = (
        #         own_launcher_data and
        #         own_launcher_data.building_type == EntityType.LAUNCHER and
        #         own_launcher_data.own_team
        #     )

        #     if not own_launcher_exists:
        #         self.own_launcher_pos = None
        #         self.rounds_without_launch = 0
        #     else:
        #         self.set_target(self.own_launcher_pos, 2, BotState.GOING_TO_TARGET)

        # # Try to place a new launcher if we don't have one
        # if self.own_launcher_pos is None:
        #     launcher_pos = self._try_build_launcher()
        #     if launcher_pos:
        #         self.own_launcher_pos = launcher_pos
        #         self.rounds_without_launch = 0
        #         self.set_target(launcher_pos, 2, BotState.GOING_TO_TARGET)
    
    def set_wandering(self):
        if not self.nearest_unexplored():
            if not (
                self.current_state == BotState.WANDERING and
                self.current_target_position.distance_squared(self.position) > 16
            ):
                enemy_base_pos = self.get_enemy_base()
                self.set_target(limit_to_map(
                    Position(enemy_base_pos.x + random.randint(-5, 5),
                            enemy_base_pos.y + random.randint(-5, 5)),
                            self.ct
                ), 16, BotState.WANDERING)
        
    def reached_target(self):        
        if self.current_state == BotState.WANDERING:
            return super().reached_target()

        if not self.is_valid_target(self.current_target_position):
            print(f"Target is invalid {self.current_target_position}")
            enemy_base_pos = self.get_enemy_base()
            self.set_target(limit_to_map(
                Position(enemy_base_pos.x + random.randint(-5, 5),
                        enemy_base_pos.y + random.randint(-5, 5)),
                        self.ct
            ), 16, BotState.WANDERING)
            return
        
        target_data = self.get_from_pos(self.current_target_position)

        if self.ct.can_fire(self.current_target_position) and not target_data.own_team:
            self.ct.fire(self.current_target_position)
            if self.ct.get_tile_building_id(self.current_target_position):
                return

        if self.position == self.current_target_position and self.ct.can_build_road(self.current_target_position):
            self.ct.build_road(self.current_target_position)

        to_build = EntityType.SENTINEL
        
        if self.current_target_type == TargetTypes.AGG_HARVESTER:
            if self.check_for_entity(self.current_target_source, CARDINAL_DIRECTIONS, EntityType.SENTINEL, self.team) or self.ct.get_tile_env(self.current_target_source) == Environment.ORE_AXIONITE:
                to_build = EntityType.BARRIER

        match to_build:
            case EntityType.SENTINEL:
                can_build = self.ct.get_action_cooldown() == 0 and self.ct.get_global_resources()[0] >= self.ct.get_sentinel_cost()[0]
                if can_build and (target_data.building_type in IGNORED_BUILDINGS or target_data.is_team_road()):
                    direction = self.current_target_position.direction_to(self.enemy_base_pos if self.enemy_base_pos else self.get_enemy_base())
                    if self.current_target_source and direction == self.current_target_position.direction_to(self.current_target_source):
                        direction = direction.rotate_left()
                    if self.position == self.current_target_position:
                        self.move_to_adjacent()

                    if self.ct.get_action_cooldown() == 0:
                        if target_data.is_team_road():
                            if self.ct.can_destroy(self.current_target_position):
                                self.ct.destroy(self.current_target_position)

                        if self.ct.can_build_sentinel(self.current_target_position, direction):
                            self.ct.build_sentinel(self.current_target_position, direction)
            case EntityType.BARRIER:
                can_build = self.ct.get_action_cooldown() == 0 and self.ct.get_global_resources()[0] >= self.ct.get_barrier_cost()[0] and self.ct.get_action_cooldown() == 0
                if can_build and (target_data.building_id is None or target_data.is_team_road()):
                    if self.position == self.current_target_position:
                        self.move_to_adjacent()
                    if target_data and target_data.is_team_road() and self.ct.can_destroy(self.current_target_position):
                        self.ct.destroy(self.current_target_position)
                    if self.ct.can_build_barrier(self.current_target_position):
                        self.ct.build_barrier(self.current_target_position)
                        if target_data.environment in ORE_SITES:
                            self.visited_ore_sites.add(self.current_target_position)


    def evaluate_aggressor_target(self, tile: Position, tile_data: TileData):
        def evaluate_harvesters():
            for d in CARDINAL_DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                check_data = self.get_from_pos(check_pos)
                if check_data.environment == Environment.WALL:
                    continue
                if check_data:
                    if check_data.bot_id and check_data.bot_id != self.id:
                        continue
                    if check_data.building_type in CAN_BUILD_OVER:
                        self.harvester_targets.append((check_pos, tile))
        
        def evaluate_conveyors():
            eval = 0
            target_tile = tile
            
            conveyor_target = get_conveyor_target(tile, self.ct)
            target_data = self.get_from_pos(conveyor_target)
            if conveyor_target and checkable_position(conveyor_target, self.ct):
                if target_data.building_type in CAN_BUILD_OVER and target_data.environment != Environment.WALL:
                    if target_data.bot_team != self.team or target_data.bot_id == self.id:
                        eval = 50
                        target_tile = conveyor_target
                      
                else:
                    next_data = self.get_from_pos(conveyor_target)
                    if next_data and next_data.building_type in TURRETS and not next_data.own_team:
                        eval += 5
                    elif next_data and next_data.building_type == EntityType.CORE and not next_data.own_team:
                        eval += 4
                    elif next_data and next_data.building_type in VALUABLE_ENEMY_ENTITIES:
                        eval += 2
                
            eval -= sum([tile.distance_squared(enemy_bot_pos) <= 2 for enemy_bot_pos in self.enemy_bots]) * 10
                        
            """
                9: titanium connecting to another conveyor belt / building
                10: refined axiomnite connecting to another conveyor belt / building
                14: titanium connecting to an enemy
                15: refined axiomnite connecting to an enemy
                19: titanium connecting to nothing
                20: refined axiomnite connecting to nothing
            """
            
            self.conveyor_targets.append((eval, target_tile))
        
        if tile_data and ((tile_data.bot_team == self.team and tile_data.bot_id != self.id) or not tile_data.building_id):
            return # Do not target ones that have a bot on them
        
        if tile_data and tile_data.building_type == EntityType.HARVESTER:
            evaluate_harvesters()
        elif self.enemy_base_pos and self.ct.get_current_round() >= 100 and tile_data.building_type in CONVEYORS:
            evaluate_conveyors()

    # def _try_build_launcher(self):
    #     if self.allied_launchers:
    #         return min(self.allied_launchers, key=lambda p: self.position.distance_squared(p))

    #     pos_data = self.get_from_pos(self.position)
    #     if pos_data and not pos_data.own_team and pos_data.building_id:
    #         if self.ct.can_fire(self.position):
    #             self.ct.fire(self.position)
        
    #     if pos_data and pos_data.is_team_road():
    #         if self.ct.can_destroy(self.position):
    #             self.ct.destroy(self.position)
        
    #     can_build = self.ct.get_global_resources()[0] >= self.ct.get_launcher_cost()[0] and self.ct.get_action_cooldown() == 0
    #     if can_build:
    #         self.move_to_adjacent()
    #         if self.ct.can_build_launcher(self.position):
    #             self.ct.build_launcher(self.position)
    #             return self.position
    
    def move_to_pos(self):
        if self.previous_position and self.previous_position.distance_squared(self.position) > 2:
            self.handle_thrown()
        super().move_to_pos()
        
        if get_skibidi_distance(self.ct.get_position(), self.current_target_position) <= 1:
            self.reached_target()
        
    def handle_thrown(self):
        self.rounds_without_launch = 0
        if self.is_valid_target(self.position):
            self.set_target(self.position, 0, BotState.GOING_TO_TARGET)
            self.reached_target()
        else:
            self.distance_map = None

    def get_ends(self, pos: Position) -> list[tuple[EntityType, Position, Team] | None]:
        if not checkable_position(pos, self.ct):
            return [None] # None signifies going out of bounds

        cached = self.conveyor_ends.get(pos, _SENTINEL)
        if cached is not _SENTINEL:
            return cached
        
        self.conveyor_ends[pos] = [] # To help with looping
        building_id = self.ct.get_tile_building_id(pos)
        building_entity = self.ct.get_entity_type(building_id) if building_id else None
        if building_entity == EntityType.SPLITTER:
            d = self.ct.get_direction(building_id)
            pos1 = pos.add(d)
            pos2 = pos.add(d.rotate_left().rotate_left())
            pos3 = pos.add(d.rotate_right().rotate_right())
            self.conveyor_ends[pos] = self.get_ends(pos1) + self.get_ends(pos2) + self.get_ends(pos3)
        elif building_entity in CONVEYORS:
            self.conveyor_ends[pos] = self.get_ends(get_conveyor_target(pos, self.ct))
        elif building_entity in IGNORED_BUILDINGS or building_entity == EntityType.ROAD:
            bot_id = self.ct.get_tile_builder_bot_id(pos)
            if bot_id:
                self.conveyor_ends[pos] = [(EntityType.BUILDER_BOT, pos, self.ct.get_team(building_id))]
            else:
                self.conveyor_ends[pos] = [(EntityType.MARKER, pos, Team.A)]
        else:
            self.conveyor_ends[pos] = [(building_entity, pos, self.ct.get_team(building_id))]
        
        return self.conveyor_ends[pos]
    
    def get_enemy_base(self) -> Position:
        if self.enemy_base_pos:
            return self.enemy_base_pos
        if not self.base_position:
            return Position(self.map_width // 2, self.map_height // 2)
        
        candidates = []
        if self.x_axis_symmetry:
            candidates.append(Position(self.base_position.x, self.map_height - 1 - self.base_position.y))
        if self.y_axis_symmetry:
            candidates.append(Position(self.map_width - 1 - self.base_position.x, self.base_position.y))
        if self.rotational_symmetry:
            candidates.append(Position(self.map_width - 1 - self.base_position.x, self.map_height - 1 - self.base_position.y))
        
        if not candidates:
            return Position(self.map_width // 2, self.map_height // 2)
        
        avg_x = sum(p.x for p in candidates) // len(candidates)
        avg_y = sum(p.y for p in candidates) // len(candidates)
        return Position(avg_x, avg_y)

    def is_valid_target(self, pos: Position) -> bool:
        tile_data = self.get_from_pos(pos)
        if tile_data is None:
            print("Tile not readable yet!")
            return False
        etype = tile_data.building_type
        if etype in CONVEYORS and not tile_data.own_team:
            ending_buildings = self.get_ends(pos)
            for e_b in ending_buildings:
                if not e_b:
                    continue
                if e_b[0] in TURRETS and e_b[2] == self.team:
                    return False 
            print("Enemy conveyor, is target")
            return True
        if etype == EntityType.LAUNCHER and tile_data.own_team:
            print("Allied launchers, is target")
            return True
        if etype in IGNORED_BUILDINGS or etype == EntityType.ROAD:
            print("Empty space, checking for harvesters or conveyors pointing...")
            
            for d in CARDINAL_DIRECTIONS:
                check_pos = pos.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                check_data = self.get_from_pos(check_pos)
                if check_data and check_data.building_type == EntityType.HARVESTER:
                    print("Has harvester next to it")
                    return True
            for d in BRIDGE_DELTAS:
                check_pos = Position(pos.x + d[0], pos.y + d[1])
                if not checkable_position(check_pos, self.ct):
                    continue
                
                end = self.get_ends(check_pos)
                if not end:
                    continue
                for ending_info in end:
                    if ending_info is None:
                        continue
                    if ending_info[1] != pos:
                        continue
                    return True
        return False
    
    def set_target(self, target_pos, distance_squared, state, target_type=TargetTypes.WANDER):
        self.current_target_type = target_type
        super().set_target(target_pos, distance_squared, state)

    def nearest_unexplored(self) -> Position | None:
        filtered_harvester_targets = list(filter(lambda x: x[0] not in self.target_black_list, self.harvester_targets))
        if filtered_harvester_targets:
            target, source = filtered_harvester_targets[0]
            self.current_target_source = source
            self.set_target(target, 0, BotState.GOING_TO_TARGET, TargetTypes.AGG_HARVESTER)
            return target
        
        filtered_conveyor_targets = list(filter(lambda x: x[1] not in self.target_black_list and (self.ct.get_current_round() > 50 or x[0] >= 0), self.conveyor_targets)) # 50 round to get economy
        print(filtered_conveyor_targets)
        if filtered_conveyor_targets:
            _, target = max(filtered_conveyor_targets, key=lambda x: x[0] * 1000 - self.position.distance_squared(x[1]))
            self.set_target(target, 0, BotState.GOING_TO_TARGET, TargetTypes.AGG_DISCONNECTED_CONVEYOR)
            return target
        
    def unreachable_path(self):
        self.target_black_list.add(self.current_target_position)
        self.set_wandering()
"""
                               -=::.         . .         ..                     .                     ............:::::::.........
                      -+=-:::-+:                                                                       ...........................
                    .=-     :.                             .    :.   ..:::::..            ..              ............::..........
                   .-           ...                                 :==+*#%##+=-.     .                        ...................
                  .=:                                      .       :--=#@@%@@@%%#+-:.                    .        .........   ..  
                 .++:          -:--=-::.                           :-#@@@@@@@@@@@@%*=::... :.                        ..           
                 -#*:..    .+++***+**+=-:--::.                    .-*@@@@@@@@@@@@@@@@@@@%*-. .                                    
          .      :+#+=-.. .####******++====---::..          ...  .:+@@@@@@@@@@@@@@@@@@@@@@*=:..   .                        .      
                  .:+*#=.=#%%####****+++==---:::..          ..-+===#@@@@@@@@@@@@@@@@@@@@@@@@%+=..   .                             
                      .--=*#%####*###*+===--::::..          .:+@@@@@@@@@@@@@@@%@@@@@@@@@@@@@@@@#:.::::. ...                       
                       .*@@@%%#####*+=-:.:::.......       .-+*%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@*++=+**+-.               .  :.    
                        +@@@%#**+=-.     .:......:..    .-*#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%%@@@#+-:             .          
==-::......            .=+-...:+=-...   --    ....:..  :#@@@@@@@@@@@@@@@@@@@@@@@@@@@@%%@@@@@@@@@@@@@@@%%=:..                      
*#*==++===-:..         .-##+-. +#=:.....:::.. .:::::..:+@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%@@@@@@@@@@@@@@@@@*-..                     
*++#%##%#++=-...      .  -%#=-:%#-....:-:::::-=-:::::.:=#@@@@@@@@@@@@@@@@%%@%%@@@@%%%%@@@@@@@@@@@@@@@%%@@@#=.  ...                
#%@@@@@@@@@#+-:...       +@%*=*@*-.::::---====--::::::-+@@@@@@@@@%@@@@@%%%#%%%%#%######%%%@@@@%%%%@@@@%%@@@%#***+:...        :.  .
@@@@@@@@@@@@%*=-:..      +@@##%@*-:::---======--:::::=%@@@@@@@%%%%@@@%%%##*++**++*****###%%%%%%%%###%%%%%@@@@@@#=:.  .        ....
@@@@@@@@@@@@@%+=-:..     :@@%%%@*-::::--===+=--:.::.-#@@@@@@%@%%%%%####***+=-===+++**##%%%%%@%%%#########%%%@@@@@+-.        .....:
@@@@@@@@@@@@@@*=-:...     :%@@%@#=::...:-===--::::::-+@@@@@%@%##%%%%###**+-:----==++*###%%%%%%%%%######%#####@@@@#-.         ...::
@@@@@@@@@@@@@@@%*-:....    .+@%%%+-::....===-::....::+@@@@@@%#%%#%%######+-:::--====+*#%%%%###%%%%###*##%####%%@@%-.         ....:
@@@@@@@@@@@@@@@@+--:...      +%%%*-.  ..:----::..:---*@@@@@@%%%#%@%%##%##*-::::=-==+***###%#%#%%%%######%#%##%%%@@+.   .      ....
@@@@@@@@@@@@@@@@@#+=-:....   .@%#+:.    .::::::.::+=+*@@@@@%%%%%@@%%###***=-::-====+++*###%#%##%###########%##%%@@@*:...  .      .
@@@@@@@@@@@@@@@*+++++*=:... . *@+:.         .:....-#@@@@@@%%%@%@%%%###+#%+=::::----==+=+*%%%%%%%##%%###%%#**#%%#%@@@@%+=-:.       
%@@@@@@@@@@@@###=-==--++:.... =#-::-=:      ....:--+#%@@@%@%##%%##%#**+%#+=-::-:::....:-=+##%#=-:-=+**#%%%####%%#%%@%#####*-      
#%@@@@@@@@@@@*+##-===--#*:.....*+=++-::...::....:==+%@@@@@%%####%####+*##*=-:::::-:-::...:+##+-...:-+*#%%%%%%##%%#%@@+:...-=:     
**%##%@@@@@@@@##%**==--=++:.....+%%#*=-:::......:+%@@@@@@@@%%%#*###*+#****=::....:=::=-::.=**-..:.-.=*%%####%%##%##@@%=.. .-:     
+*%**#%@@@@%##%#*=+%#%+=+---.....=@#=...:....   :*@@@@%####%@%###**+=##*##=-:.:::-. .--:..=#+:..:=-++*%%%#**#####%%%@@=.   .:     
###*+#%@@@@@@%%*****+**#%*+++-.  .+%%%#+-:..    .+%@@##%%@@@%%###*=--+*+*#=:::-==:.::-=--:=%#+--+-:=##*###***#*###%%@%=..         
+*+=%%@@@@##@###*++*+==+**=::=..  .+%#*-...       :*##%*####%%%##+-:::==*#+:..----::::--::=#%#+==+++**+***+*##***#%%@@-.          
=+*+#@@@@@@@@##%*=+#%@++#==+---.   ..:-:.           .=*++==*%%###*=++-.-*@%+-:-===-=+==-..:+%#%#****+=+**++*#######%@@@*=-.       
=+*##@@@@@@@@#**#+==+*++#=--::...:=.      .:.        .-=:::-+*******-::*@@@#+=--=+++++-...-*%##*##**++===+**##%##%%##*+-.         
-*#+#@@@@@@@@#+*##=++-=*=--::.:+#+-.   :+*-      .   :=+*++=-==++==**===#@@%#=+=+**++-. .--*%%%*+*##+-=-:+*#%%%@%%%#+-:.          
#+***%@@@@@@@%##*%+*=-++---:-#%%=     =*-.   .. ..  #@%#****++++-:::=#**+@@@#*==+**=::*==+-=####*==*#*::-+****#%#**+:....         
---*%#@@@@@@@@%#*%*#+=%===+%@@@@*.   --  .. ...... *@@%#****+++==:.:::#*+#@@%=-=+=::. . .=-.-==+==--+##-..:==:====-:..            
:-+#++@@@@@@@@%#+*%###-+###@@@@=    ..............-@@@%####*+====----*:-*+%@+::====:::.    ...:+****++**:.... ........:      .... 
--+#*+%@@@@@@@%#%@#=*%*#%@@@@@+     ...::...:....:#@@@##**###+=-=-:.-=:.  *#:.-=++=---:... .:-++**#%%%##=.      .   .. ......::::.
-==+%++#@@@@@@@@%#*#%%%%%%%%@@-.-++=---:..:::....:%@@%#**####=+=--=#%-=:..*+.:-====-===---===+*+*+*#%#%%=..  .  ..........:::-::::
-+#**#+*@%@@@@@@@#%%@@@@@%@@@##+. ..:-:..:::.. ..-@#@@####%%#-===+@%*-.   =+.:-:-:::-::=::+====-+*+*#%%%=... .  .......::::::-::::
*#++##%@@%@@@@@@@@@@@@@@@@@@%+:+*::=+-:::::...  .+%#@@#%##%%*=-=#@#*+=.   .-....... .  . .. :...-===+=*+:.    ......::::----------
==+*=+**@@@@@@@@@@@@@@@@@@@@+-..-*@*#=:-:::..   :#+#@%#%*#@%+==%%**+++=:.     einstein      .....:::===-..     .....::------=====--
==*+=*#*@@@@@@@@@@@@@@@@@@@#-:.:==%=+#=-:...    :#+@%*#%#%@#+#@@#*+++++=:               ...:-=+++**=:.   .   ....::---===++++++==-
-**==#+#%#@@@@@@@@@@@@@@@@@===:==--#==%-...     .+%%+*%%#@%#@@@%#++++++++:           ..-=++*+++*-..   ..  .....:::---==++******+=-
=*++*=-+@%@@@@@@@@@@@@@@@@*=--+==+#==-:=- .      =@**#%%@%%@@@@%#+++++++++-             .:.:-+-.....     .....::---==++*######*+--
#=+#*=-=#@@@@@@@@@@@@@@@@@%*+++--*+::.  .:       =%#*#%%@%%@@@@%#==++++++++-               .:::.... .   .....::--===+*#%%%%%%#*+--
=-=+++=+#@@@@@@@@@@@@@@@@@@%*+=+#=:...           .##*%%@%#@@@@@#*-=+++++++++:.....     .:.  .:-==:      ....:::--=+*#%%%@@@@@%#=-:
::--#=++%@@@@@@@@@@@@@@@@@@@#*%+-:...             -%*%%@#%@@@@%+-::=++++++++**++==+-  .    +**+...    ......::---=+###%@@@@@@#=-:.
-:::+==+%@%+#@@@@@@@@@@@@@@@@*--:..                *#%%@#@@@@%*+---::-==++++**+***+**-    =**##:.     ..::.::---=+*##%%%@@@%+=:.. 
-+-::++#*@@#=*@@@@@@@@@@@@@@#=-:..                  -@%@%@@@@%*=-----:---++++++++****#*:  :*##%+.     :-+=::----=+***#*##*+=-.... 
..=-:==#++%%*=+@@@@@@@@@@@@@#+:...                  :%@%%@@@@%*+=---==--::-=+++**+*##*##-  *##%*.   ..::+:::--++=+++++==-=-:....  
....:-*##++#%*=+%@@@@@@@@@@@*+-..                   :#%%#@@@@@%##=--=+==--::-=++*#-*%###%* :#%%*... .-:+:::--=-+--=+====--:::.... 
......+*#%*=#*+===%@@@@@@@@%++-:                   -@@@%%@@%%@@%#*---==+==-:.:-+**:-#%##*#%=.*##. .-----=--=--+*=----:::::....    
     ..:#%#+--+++===+*******+=-:.            =#*=::@@%#+*@@*=%@@#%+--==+++==:.:=+*.:*%#**#%@#=*#:.:::::::=*===-+-:---::::....     
        .+#*++***+==========++=-:   ..   .-*%%##%****##+=@@#==@@%%%+-====+++=-.:+*::=##**#@@@*-#*:..-+-:::=+=-==::==-:.::.:..   ..
          :**###**+==+*+++++++--:=-%%#%%**+++**#%%*+++++=#@%+=#@@%@%+--===++++-.=*::-++**####*-.:+=-:-+*=::+*:.::+-+::..       .  
             :=+**+=+++****+++=-=**++**++**#***#%%%*===+++%@@++@@%@@#--===+***#--=::=+*++==+*#%@#--*-::+***=:::=--+=..::.  :--::: 
                .-***+++****+++=*##*===+==+++++*%%*#+--=*+*%@@##@@@@@+-===++==++-:-++======+*#%@@@+:*+===-.:::=--=+::.:-:.:==*#+*.
                    .=##***+++++****+=++=-==++++++##*=--+*#+%%%@%@@@@#====-=====--=----==++++*###%%=-=. .-*+=-:-=*=. .:-=+==+==*- 
                       .-+*+++*%**+*++++-=++=--=*###+=--+*+=-@%#@@@@@@*===-::::-+=:----+*=-==+#%%%##%%#%#*+...:-==+*--==:-++=+#:  
                        .==*#%******+++=====+++*###+==--=+=:.#@#+%@@@@%+==========+===+++++++====+=--==++=-: .:::----::-==-=*+    
                         ---+**+*#*+**+==++******+==++=-==-:.:@@#+%@@@@#========--:--=-:======-:==-::-------- .::-:::-=+==*-.     
                          ::......-*##*+==+**++***==++=--:.  :@@@#*@@@@%*=------------:.:==+=:::-++-.::-----=-.:----=++**:        
                          .....        .:-+*+=+++==--::..    .%@@@%#@@@#%#=----------::..-=+=-..:=+=..::-==--++-                  
                          .=:..                               +@@%@%@@@*+#%*=--------:...:-====:::=+=::--==+=+*=                  
                          . ....                              .*@@#**%@%*=-*%#=----:::::::::--====-::=+*++-.                      
                          :  ...                                +@@%*++++**##%@%*=--:::::::------=++-.+=                          
                          .   ..                                 -@@@@*+=-----:::=*##*++++++++******:--                           
                              ..                                  @@@%##*=---:::::::::----=+++++++**=-:                           
                              .::.                               .@@@*+++--:::::::::::::----===+====-.                            
                               :.....                             +%#+===-::::::::::::::::::--::::::..                            
                               .....                               =+=---::........:::::::::.........                             
                               ..                                    -::.....................                                     
"""