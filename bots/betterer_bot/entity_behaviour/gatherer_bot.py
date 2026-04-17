from cambc import Controller, Environment, Position, EntityType
from utils.tile_info import TileData
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class Gatherer(Bot):
    def __init__(self, ct: Controller):
        self.harvester_count = 0
        self.titanium_harvester_count = 0

        self.axionite_ore_sites = set()

        super().__init__(ct)

    def update_tile(self, tile: Position, tile_data: TileData):                
        if tile_data.environment == Environment.ORE_TITANIUM:
            if tile not in self.ore_sites and self.current_state == BotState.WANDERING:
                self.set_wandering()
            self.ore_sites.add(tile)
        elif tile_data.environment == Environment.ORE_AXIONITE:
            if tile not in self.axionite_ore_sites and self.harvester_count > 1 and self.current_state == BotState.WANDERING:
                self.set_wandering()
            self.axionite_ore_sites.add(tile)
    
        if (
            self.current_state == BotState.GOING_TO_TARGET and
            self.current_target_position == tile
        ):
            if tile_data.bot_id != self.ct.get_id() and tile_data.bot_team == self.team:
                self.set_wandering()
            elif (
                not (self.is_passable(tile) or tile_data.destroyable()) or \
                (tile_data.own_team and tile_data.building_type in CONVEYORS) or \
                not any([self.is_passable(tile.add(d)) for d in CARDINAL_DIRECTIONS])
            ):
                print("Yeah no fuh that")
                self.set_wandering()
        

    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        print(f"Trying to build road at {move_pos} {self.current_state}")
        move_data = self.get_from_pos(move_pos)
        tile_data = self.get_from_pos(self.position)
        if move_data is None or tile_data is None:
            print("Not updated yet!")
            return super().build_road(move_pos, next_pos)
        
        # This runs 4 extra checks each tick idk if its good or not
        if self.build_harvester():
            print("Need harvesters")
            return False
        
        if self.current_state != BotState.GOING_BACK:
            return super().build_road(move_pos, next_pos)

        same_team = tile_data and tile_data.own_team

        if self.ct.can_fire(self.position) and not same_team:
            self.ct.fire(self.position)

            # This checks if the building is still alive
            if self.ct.get_tile_building_id(self.position):
                return False
        
        new_building_id = self.ct.get_tile_building_id(self.position)

        if (new_building_id is None or tile_data.is_team_road()) and tile_data.environment not in ORE_SITES:
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
                    True, 
                    DeltaTypes.BRIDGE, 
                    self.ct,
                    0, 
                    True
                )
            case BotState.WANDERING:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    True, 
                    DeltaTypes.ALL, 
                    self.ct,
                    self.target_distance_squared,
                    False
                )
            case BotState.GOING_TO_TARGET:
                self.distance_map = self.path_finder.run(
                    self.position,
                    self.current_target_position,
                    True, 
                    DeltaTypes.ALL, 
                    self.ct,
                    self.target_distance_squared, 
                    True
                )
    
    def reached_target(self):
        print(f"Reached target timer {self.ct.get_cpu_time_elapsed()}")
        if self.current_state == BotState.WANDERING:
            return super().reached_target()
        self.position = self.ct.get_position()
        position_data = self.get_from_pos(self.position)
        if position_data and position_data.building_type == EntityType.CORE and position_data.own_team:
            return super().reached_target()
        target_data = self.get_from_pos(self.current_target_position)
        same_team = target_data and target_data.own_team

        if not same_team:
            if self.ct.can_fire(self.current_target_position):
                self.ct.fire(self.current_target_position)

        reached_ore = self.current_state == BotState.GOING_TO_TARGET and target_data.environment in ORE_SITES
        can_build = self.ct.get_global_resources()[0] >= self.ct.get_harvester_cost()[0]
        
        print(f"Reached ore {reached_ore}")
        if reached_ore:
            for d in CARDINAL_DIRECTIONS:
                check_pos = self.position.add(d)
                if not checkable_position(check_pos, self.ct):
                    continue
                tile_data = self.get_from_pos(check_pos)
                if tile_data.bot_id:
                    continue
                if (tile_data.building_type in IGNORED_BUILDINGS or tile_data.is_team_road()) and tile_data.environment != Environment.WALL:
                    if self.ct.can_destroy(check_pos):
                        self.ct.destroy(check_pos)
                    if self.ct.can_build_barrier(check_pos):
                        self.ct.build_barrier(check_pos)
                    return

        print(f"Barrier check done {self.ct.get_cpu_time_elapsed()}")
        if reached_ore and can_build:
            self.set_target(self.base_position, BASE_DIST, BotState.GOING_BACK)
        elif self.current_state == BotState.GOING_TO_TARGET:
            if self.position.distance_squared(self.base_position) <= BASE_DIST:
                if self.ct.can_destroy(self.current_target_position) and target_data.is_team_road():
                    self.ct.destroy(self.current_target_position)
                    
                if target_data.building_type in IGNORED_BUILDINGS:
                    bridge_target_pos_choices = self.get_positions_of_entities(self.current_target_position, 9, EntityType.SPLITTER, self.team)
                    bridge_target_pos = random.choice(bridge_target_pos_choices) if bridge_target_pos_choices else None
                    if bridge_target_pos and self.ct.can_build_bridge(self.position, bridge_target_pos):
                        print("Built through reached target")
                        self.ct.build_bridge(self.position, bridge_target_pos)
                
                print(target_data.building_type)
                if (target_data.building_type in CONVEYORS or target_data.building_type == EntityType.CORE) and same_team and not self.build_harvester():
                    self.set_wandering()
            else:
                print("Not quite there yet")
                self.set_target(self.base_position, BASE_DIST, BotState.GOING_BACK)
        
    
    def nearest_unexplored(self):
        unvisited_ores = None
        if self.harvester_count <= 1 or self.titanium_harvester_count <= 0.75 * self.harvester_count:
            unvisited_ores = self.ore_sites - self.visited_ore_sites
        else:
            unvisited_ores = self.ore_sites.union(self.axionite_ore_sites) - self.visited_ore_sites
        print(f"Unvisited: {unvisited_ores}")
        unvisited_ores = set(
            filter(
                lambda p: (
                    (self.enemy_base_pos is None) or self.base_position.distance_squared(p) <= 1.8 * self.enemy_base_pos.distance_squared(p)
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
        print("Setting wandering")
        next_pos = self.nearest_unexplored()
        if next_pos:
            self.set_target(next_pos, 0, BotState.GOING_TO_TARGET)
        else:
            next_pos = super().nearest_unexplored()
            self.set_target(next_pos, 16, BotState.WANDERING)

    def set_target(self, target_pos, distance_squared, state):
        return super().set_target(target_pos, distance_squared, state)
    
    
    def build_conveyor_chain(self, from_pos: Position, to_pos: Position):
        print("Called build conveyor chain")
        from_data = self.get_from_pos(from_pos)
        if self.ct.can_destroy(from_pos) and (from_data.destroyable() or from_data.is_team_road()):
            self.ct.destroy(from_pos)

        bridge_target_pos_choices = self.get_positions_of_entities(from_pos, 9, EntityType.SPLITTER, self.team)
        p = self.ct.get_position()

        if bridge_target_pos_choices:
            bridge_target_pos = random.choice(bridge_target_pos_choices)
            print(f"Trying to build bridge from {from_pos} to {bridge_target_pos}")
            if self.ct.can_build_bridge(from_pos, bridge_target_pos):
                self.ct.build_bridge(from_pos, bridge_target_pos)
                self.set_wandering()
            return
        elif from_pos.distance_squared(self.base_position) <= 18:
            print(f"Trying to build bridge from {from_pos} to {self.base_position}")
            if self.ct.can_build_bridge(from_pos, self.base_position):
                self.ct.build_bridge(from_pos, self.base_position)
                self.set_wandering()
            return

        print(f"Building conveyor chain from {from_pos} to {to_pos}")
        if self.position.distance_squared(from_pos) > 1:
            print("Too far away!")
            self.set_target(from_pos, 0, BotState.GOING_TO_TARGET)
            return

        same_team = from_data and from_data.own_team
        
        if same_team and from_data.building_type in CONVEYORS:
            print("Reached existing chain")

            if not self.build_harvester(p):
                self.set_wandering()
            return
        
        dir = from_pos.direction_to(to_pos)
        if from_pos.distance_squared(to_pos) > 1 or get_skibidi_distance(to_pos, self.base_position) == 2:
            if self.ct.can_build_bridge(from_pos, to_pos):
                self.ct.build_bridge(from_pos, to_pos)
                
                self.set_target(to_pos, 0, BotState.GOING_TO_TARGET)
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
            
"""
                                   :---.            ..      ..   .:.                       . ....                                 
                                  :--.  .  ...                    :.                            :.                                
                                 :-:.   ..:....                                                  :.                               
                                ::-.                                                             ..                               
                                --:.               .::::::::::::::::....::.....               .::..                               
                                --..            .--==+++++++++++++==========----:..          .:--:                                
                               :--:           :-=+***###########**********+++===--::.           .::                               
                               ---...       :=+**#######%%%##%##########*****+++=---:::.        :::                               
                               -=-:.       -+**###%%%%%%%%%%%%%%#########******++=-----:.       .::                               
                               -=-:      :-**####%%%%%%%%%%%%%%%#######*##*#***+++==----::.    ..::                               
                               ==-.     -+**##%%%%%%@%%%%%%%%%%%%######****#****+++==----:::      ::                              
                              =-=-.   .-+*###%%%%%@%%@@%%%%%%%%%%#######*#*******+++==----:::..    .                              
                             ---=-.  .-+###%%%%%%@%@@%%%%%%%%%%%%#%######*##******++===----:-::    ..                             
                             ---=-:  -+*%%%%%%%%@%@@%@%%%%%%%%%###########*#*****++++==----::-:    ..                             
                             -----:.-+*#%%%%%%%@%@%@%%%%%%%%%#%###########**#****+++===----:-::    ..                             
                             :-:--.:=+#%%%%%%%%%@@@@%%%%%%%%%#############******+++====----:-::.    .                             
                             --:--:-=*##%%%%%%@@%@%@@%@%%%%%%%%%###########****++++====---:::::.   .                              
                              ----:-=+##%%%%%%%%%@%%%%%%%%%%%%#######%%%###***+++++===----::::.    ..                             
                              ----::-+*%%%%%%%%%%%%%%%%%%%######%########****++++=====---:::::.    ..                             
                               --:.:-+*#%#%%%%%#*****+++=-==+*#########***+=-----:------::::::.                                   
                               --:.:-=*#%%%%%##**+++=------==+***#*##****+=--:::-------:...:::.     .                             
                               --:.:-=*##%%%#***+*#####*********#####*+==-----=+++++==---:..::.     .                             
                               --::.-=*#%#######%#%####**+++++**#####*=-::-----===-=------::.::.                                  
                                --.::-*#%%########*+=-:...:---=**##%#*-. ..:--:.   ...:---::.:..                                  
                                --.::-+#%#%####*+==--.:. .=---=+**#%#+-.   .-=--: .:.  .:-::..:.                                  
                                +*-::-=#%%####**+=-=+++===----=*#####*-: ..:-=+===----::::-::.:.                                  
                                ##*=---##%%#%##**######*+=---=+**####*=-...::---------------:::.                                  
                               #*+##=:-#%%%%#%%%%####****+****#######*=-:::-----====++++==---:::. ..                              
                               #**##*--##%%%%%%%%%%######***########%#+-:::---======++++==---:::.  ..                             
                               **%%%*==#%%%%%%%%%%###########%%%%%####+-::---=++***+++++==----::.  .                              
                               #%%#*+=+#%%%%%%%%%%%%%%#%%####%%%#####%*+--:::-=********+==----::.  .                              
                               %%%#***+#%%%%%%%%%%%%%%%%###**#####%%%%#*+=--::-+#####***+=----::.  .                              
                               %%%**####%%%%%%%%%%@%%%%##**++**##%%%%%##*--:-::+*####***+=----::..:::                             
                                %%#*####%%#%%%%%@@@@%%##*+++*#########**+-.:::-=+*###***+==--::...::.                             
                                %%%%%####%%%%%%%%%%%%%**=-+*##**+=-=+*+=-. ...--=+**#**++=---::...::.                             
                                %%@@@@%**#%%%%%%%%%%##+-=+*+#*******++--::...::---=++**++=---:......                              
                                 %%@%%%#*###%#*###%##+=+*####***+++++=---:...::-----=+**+=--::..                                  
                                  ##%%%**#######%%%#*=+++***###*****=---=-----------==+*+=-:::..                                  
                                       ++#########%#+****##%####**+*++=---:::::---====+#*--:::..                                  
                                       ++**######%%%+#****=---=-===---::....... .:=+++*#+-::::.                                   
                                        +**##*#**##%#####%%%#*****#**+++=---::::--=+**##=-:::..                                   
                                        ***####*+##%%%%#%%%%%%%%%%%##*++==-------==++##+-:.:..                                    
                                         ****###***##%%%%%%%%%%%%%###***++===---====+*+-::..                                      
                                         ##***#*++=+#####%%%%%%%%%##**+==+===-======+=-::.                                        
                                         %%*++++****##**#%%%%%%%%%%#**+++++=======---::...                                        
                                         %%#+=+****#**#**##%%%%%%%%#**+++===+++==--:...                                           
                                         %%%*+==++**##*++#**###%%###**+==--====--::                                               
                                         %%%#++--=+******#*##**###*#*++=--------:..                                               
                                         %%%%#*=--=+**++=++++*###+*+*===-------:.                                                 
                                         %%@%##+=---====-==+=++**++**++=----:::.                                                  
                                        @@%%%%#*+=---------=-=+++++*+==----:::.                                                   
                                      *%@@%@%%##**+=----------=-======--::::..                                                    
                                     .-@@@%%%%%###*++-------::---------:::..                                                      
                                      #@@@@%@%%%%#*++++=----::-:::-:::::...          .                                            
                                     .@@@@@%%@%%%%#***+++=---::--------:::.         ...                                           
                                     -@@@@@@@@%%%%##****++===---------::.. ....   .....                                           
                                     =@@@@@@@@@@%%%###***+*+++====--------::. .. ....:-                                           
                                     -@@@@@@@@@@@@%%####****+++++==+++==----:........-=-                                          
                                     -@@@@@@@@@@@@@@@%####***+++******++=----:::::::-+=-:                                         
                                     .%@@@@@@@@@@@@@@@@@%####**********++=-------::-+==:                                          
                                      *@@@@@@@@@@@@@@@@@@@@@%***####****+==-------+*+=-.                                          
                                      -@@@@@@@@@@@@@@@@@@@@@@@@@%****#***++===-+##*+==-                                           
                                      .%@@@@@@@@@@@@@@@@@@@@@@@@@@@%*+====+++*%@#*+++=-                                           
                                       -@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%%#%#@@@@#**+++==.                                          
                                        -%@@@@@@@@@@@@@@@@@@@@@@@@@@%#%@@@@#@@%#**+++==:                                          
                                         :#@@@@@@@@@@@@@@@@@@@@@@@#:=#*-     :*#*++++==-                                          
                                          :*@@@@@@@@@@@@@@@@@@@@@-             :++++====-                                         
                                           :*%@@@@@@@@@@@@@@@@@+    .            =++====-.                                        
                                            .*%@@@@@@@@@@@@@@@:                  :=+=+=+=-                                        
                                             :#@@@@@@@@@@@@@%=*#%=   .            -=+++*+=.                                       
                                               *@@@@@@@@@@@%%%%@@@*             . .-+++*++-                                       
"""