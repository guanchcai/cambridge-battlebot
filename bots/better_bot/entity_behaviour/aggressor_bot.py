from entity_behaviour.bot import Bot
from utils.constants import *
from utils.constants import _SENTINEL
from utils.helper_functions import *
from cambc import Controller, Position, Direction, EntityType, Environment, ResourceType
import random
from itertools import product

class Aggressor(Bot):
    def __init__(self, ct: Controller):
        self.aggression_targets = []
        self.turrets_in_range = []

        self.own_launcher_pos = None
        self.enemy_launchers = set()
        self.allied_launchers = set()
        self.rounds_without_launch = 0
        self.conveyor_ends = {}
        self.listening = False
        super().__init__(ct)

    def set_wandering(self):
        self.aggression_targets = []
        self.set_target(self.nearest_unexplored(), 16, BotState.WANDERING)

    # def move_to_pos(self):
    #     position = self.ct.get_position()
    #     super().move_to_pos()
    def run_tick(self, ct):                
        return super().run_tick(ct)

    def build_road(self, move_pos: Position, next_pos: Position):
        print(f"Trying to build road at {move_pos}")
        if self.ct.can_build_road(move_pos):
            self.ct.build_road(move_pos)
        return True
    
    def run_flood_fill(self):
        print(f"Going from {self.ct.get_position()} to {self.current_target_position} and ignoring walls = {self.target_distance_squared == 0}")
        self.distance_map = self.path_finder.run(
            self.ct.get_position(),
            self.current_target_position,
            True, 
            DeltaTypes.ALL, 
            self.target_distance_squared, 
            self.target_distance_squared == 0
        )

    def update_map(self):
        self.aggression_targets = []
        self.turrets_in_range = []
        self.enemy_launchers = set()
        self.allied_launchers = set()
        self.conveyor_ends = {}
        super().update_map()

        # Store all the bot launchers of enemies as a set
        # Loop through the set and set all positions nearby as walls using set_from_pos (or you can alternatively set it as update tile detects if it is a launcher)
        # If path finder can't find a path (Returns None) yet there is a target (current_target_position is not None) then:
        # Place a launcher (if possible) - if not then... uhh
        # Set target to the launcher
        # In launcher script, identify the target using the same logic (thus it should identify the same target as the bot, if not its fine as it is still "a" target)
        # Launch set bot to the target
        
        # Add if you have time:
        # If the launcher doesn't launch myself for more than 3 rounds in a row (meaning there is not targets nearby), destroy the launcher
        # This is because we blindly path find to a bot launcher trusting that it has a target

        # 1: Loop through enemy launchers and mark nearby tiles as walls
        for launcher_pos in self.enemy_launchers:
            print(launcher_pos)
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    if dx * dx + dy * dy <= TURRET_THREAT_RADIUS:
                        wall_pos = Position(launcher_pos.x + dx, launcher_pos.y + dy)
                        if is_in_bound(wall_pos, self.ct):
                            self.set_from_pos(self.internal_map, wall_pos, Environment.WALL)
                        
                            if self.distance_map and wall_pos in self.distance_map and wall_pos != self.current_target_position:
                                print(f"Encountered wall in path on position: {wall_pos}")
                                self.distance_map = None

        # 2: Pick best target if not already hunting
        if self.current_state != BotState.GOING_TO_TARGET:
            if self.aggression_targets:
                _, best_target = max(self.aggression_targets)
                self.set_target(best_target, 0, BotState.GOING_TO_TARGET)

    def update_tile(self, tile: Position, building_id: int | None, bot_id: int | None):
        etype = self.ct.get_entity_type(building_id) if building_id else None

        if self.current_state == BotState.GOING_TO_TARGET and tile == self.current_target_position:
            if bot_id and bot_id != self.ct.get_id() and self.ct.get_team(bot_id) == self.team:
                self.set_wandering()
            
            if self.ct.is_tile_empty(tile) or is_team_road(tile, self.ct):
                self.target_distance_squared = 2
                self.distance_map = None
            elif building_id and etype not in PASSABLE:
                # Don't wander off if this is our own launcher we're trying to use
                if etype == EntityType.LAUNCHER and self.ct.get_team(building_id) == self.team:
                    pass
                else:
                    self.set_wandering()
    
        if building_id is None or (bot_id and bot_id != self.ct.get_id() and self.ct.get_team(bot_id) == self.team):
            return
        
        same_team = self.team == self.ct.get_team(building_id)
        if not same_team:
            if etype in TURRETS:
                self.turrets_in_range.append((tile, etype, self.ct.get_direction(building_id)))
            elif etype == EntityType.LAUNCHER:
                self.enemy_launchers.add(tile)
            else:
                self.evaluate_aggressor_target(tile, building_id, bot_id, etype)
        elif etype == EntityType.LAUNCHER and not (
            check_for_entity(self.ct.get_position(), self.ct, DIRECTIONS, EntityType.CONVEYOR, self.team) or \
            check_for_entity(self.ct.get_position(), self.ct, DIRECTIONS, EntityType.SPLITTER, self.team) or \
            check_for_entity(self.ct.get_position(), self.ct, DIRECTIONS, EntityType.BRIDGE, self.team)
        ):
            self.allied_launchers.add(tile)
        
    def unreachable_path(self):
        if self.current_state == BotState.WANDERING:
            return super().unreachable_path()
        # Check if we already have a launcher built
        if self.own_launcher_pos is not None:
            own_launcher_id = False
            if checkable_position(self.own_launcher_pos, self.ct):
                own_launcher_id = self.ct.get_tile_building_id(self.own_launcher_pos)
            
                own_launcher_exists = (
                    own_launcher_id and
                    self.ct.get_entity_type(own_launcher_id) == EntityType.LAUNCHER and
                    self.ct.get_team(own_launcher_id) == self.team
                )
            else:
                own_launcher_exists = True


            if not own_launcher_exists:
                self.own_launcher_pos = None
                self.rounds_without_launch = 0
            else:
                self.set_target(self.own_launcher_pos, 2, BotState.GOING_TO_TARGET)

        # Try to place a new launcher if we don't have one
        if self.own_launcher_pos is None:
            launcher_pos = self._try_build_launcher()
            if launcher_pos:
                self.own_launcher_pos = launcher_pos
                self.rounds_without_launch = 0
                self.set_target(launcher_pos, 2, BotState.GOING_TO_TARGET)

    def nearest_unexplored(self) -> Position | None:
        t_pos = self.get_enemy_base()
            
        return limit_to_map(
                Position(t_pos.x + random.randint(-5, 5),
                        t_pos.y + random.randint(-5, 5)),
                        self.ct
            )

    def reached_target(self):
        if self.current_state == BotState.WANDERING:
            self.set_target(self.nearest_unexplored(), 16, BotState.WANDERING)
            return
        
        building_id = self.ct.get_tile_building_id(self.current_target_position)
        target_entity = self.ct.get_entity_type(building_id) if building_id else None
        
        if target_entity == EntityType.LAUNCHER:
            
            if self.rounds_without_launch >= 3:
                if self.ct.can_destroy(self.own_launcher_pos):
                    self.ct.destroy(self.own_launcher_pos)
                self.own_launcher_pos = None
                self.rounds_without_launch = 0
                return

            self.rounds_without_launch += 1
            self.listening = True

        if not is_valid_target(self.current_target_position, self.ct):
            print(f"Target is invalid {self.current_target_position}")
            self.set_target(self.nearest_unexplored(), 16, BotState.WANDERING)
            return            

        same_team = building_id and self.ct.get_team(building_id) == self.team
        p = self.ct.get_position()
        if self.ct.can_fire(p) and not same_team:
            self.ct.fire(p)

        to_build = EntityType.SENTINEL
        
        is_harvester = check_for_entity(self.current_target_position, self.ct, CARDINAL_DIRECTIONS, EntityType.HARVESTER, other_team(self.team))

        if is_harvester:
            if check_for_entity(is_harvester, self.ct, CARDINAL_DIRECTIONS, EntityType.SENTINEL, self.team):
                to_build = EntityType.BARRIER

        match to_build:
            case EntityType.SENTINEL:
                can_build = self.ct.get_global_resources()[0] >= self.ct.get_sentinel_cost()[0] and self.ct.get_action_cooldown() == 0
                if can_build and (target_entity in IGNORED_BUILDINGS or is_team_road(self.current_target_position, self.ct)):
                    direction = self.current_target_position.direction_to(self.enemy_base_pos if self.enemy_base_pos else self.get_enemy_base())
                    
                    if p == self.current_target_position:
                        self.move_to_adjacent()

                    if is_team_road(self.current_target_position, self.ct):
                        if self.ct.can_destroy(self.current_target_position):
                            self.ct.destroy(self.current_target_position)

                    if self.ct.can_build_sentinel(self.current_target_position, direction):
                        self.ct.build_sentinel(self.current_target_position, direction)
            case EntityType.BARRIER:
                can_build = self.ct.get_global_resources()[0] >= self.ct.get_barrier_cost()[0] and self.ct.get_action_cooldown() == 0
                if can_build and (building_id is None or is_team_road(self.current_target_position, self.ct)):
                    
                    if p == self.current_target_position:
                        self.move_to_adjacent()

                    if is_team_road(self.current_target_position, self.ct):
                        if self.ct.can_destroy(self.current_target_position):
                            self.ct.destroy(self.current_target_position)

                    if self.ct.can_build_barrier(self.current_target_position):
                        self.ct.build_barrier(self.current_target_position)


    def evaluate_aggressor_target(self, tile: Position, building_id, bot_id, entity_type):
        def evaluate_harvesters():
            for d in CARDINAL_DIRECTIONS:
                check_pos = tile.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                b_entity = get_entity(check_pos, self.ct)
                bot_id = self.ct.get_tile_builder_bot_id(check_pos)
                if bot_id and bot_id != self.ct.get_id():
                    continue
                if self.ct.get_tile_env(check_pos) != Environment.WALL and (b_entity in IGNORED_BUILDINGS or b_entity == EntityType.ROAD):
                    self.aggression_targets.append((100, check_pos))
                # elif b_entity in PASSABLE and b_entity != EntityType.CORE:
                #     self.aggression_targets.append((50, check_pos))

            """
                50: harvesters next to a passable (conveyors for example) this can be toned back down
                100: harvesters with nothing next to them
            """
        
        def evaluate_conveyors():
            resource = self.ct.get_stored_resource(building_id)
            eval = 0
            target_tile = tile

            conveyor_end = self.get_ends(tile)
            if not conveyor_end:
                return
            
            for end_building in conveyor_end:
                if end_building is None:
                    return
                if end_building[1] == self.team and (end_building[0] in TURRETS or end_building[0] == EntityType.BUILDER_BOT):
                    return

            match resource:
                case ResourceType.REFINED_AXIONITE:
                    eval = 10
                case ResourceType.TITANIUM:
                    eval = 9
                case _:
                    return
            
            conveyor_target = get_conveyor_target(tile, self.ct)
            if conveyor_target and checkable_position(conveyor_target, self.ct):
                b_id = self.ct.get_tile_builder_bot_id(conveyor_target)
                if b_id is None and get_entity(conveyor_target, self.ct) in IGNORED_BUILDINGS:
                    eval += 8
                    target_tile = conveyor_target
            if is_directly_connected_to_turret(tile, other_team(self.team), self.ct):
                eval += 5
            """
                9: titanium connecting to another conveyor belt / building
                10: refined axiomnite connecting to another conveyor belt / building
                14: titanium connecting to an enemy
                15: refined axiomnite connecting to an enemy
                19: titanium connecting to nothing
                20: refined axiomnite connecting to nothing
            """
            
            self.aggression_targets.append((eval, target_tile))
        
        if bot_id or not building_id:
            return # Do not target ones that have a bot on them
        
        if entity_type == EntityType.HARVESTER:
            evaluate_harvesters()
        elif self.enemy_base_pos and tile.distance_squared(self.enemy_base_pos) <= 13 ** 2 and entity_type in CONVEYORS:
            evaluate_conveyors()

    def _try_build_launcher(self):
        print("Yo I need a launcher here")
        if self.allied_launchers:
            return min(self.allied_launchers, key=lambda p: self.position.distance_squared(p))

        building_id = self.ct.get_tile_building_id(self.position)
        if building_id and self.ct.get_team(building_id) != self.team:
            if self.ct.can_fire(self.position):
                self.ct.fire(self.position)
        
        if is_team_road(self.position, self.ct):
            if self.ct.can_destroy(self.position):
                self.ct.destroy(self.position)
        
        can_build = self.ct.get_global_resources()[0] >= self.ct.get_launcher_cost()[0] and self.ct.get_action_cooldown() == 0
        if can_build:
            self.move_to_adjacent()
            if self.ct.can_build_launcher(self.position):
                self.ct.build_launcher(self.position)
                return self.position
    
    def move_to_pos(self):
        if self.previous_position and self.previous_position.distance_squared(self.position) > 2:
            self.handle_thrown()
        
        return super().move_to_pos()
        
    def handle_thrown(self):
        print("yo???")
        self.rounds_without_launch = 0
        if is_valid_target(self.position, self.ct):
            self.set_target(self.position, 0, BotState.GOING_TO_TARGET)
            self.reached_target()

    def get_ends(self, pos: Position) -> list[tuple[EntityType, Team] | None]:
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
                self.conveyor_ends[pos] = [(EntityType.BUILDER_BOT, self.ct.get_team(building_id))]
            else:
                self.conveyor_ends[pos] = [(EntityType.MARKER, Team.A)]
        else:
            self.conveyor_ends[pos] = [(building_entity, self.ct.get_team(building_id))]
        
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
==+*=+**@@@@@@@@@@@@@@@@@@@@+-..-*@*#=:-:::..   :#+#@%#%*#@%+==%%**+++=:.                  .....:::===-..     .....::------=====--
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