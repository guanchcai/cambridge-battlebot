from cambc import Controller, Environment, Position, EntityType, ResourceType
from utils.tile_info import TileData
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class BaseBuilder(Bot):
    def __init__(self, ct: Controller):  
        self.potential_targets = []      
        super().__init__(ct)

    def update_tile(self, tile, tile_data: TileData):
        if not checkable_position(tile, self.ct):
            print(f"Something is weird for: {tile}")
            return
        
        del_x = abs(tile.x - self.base_position.x)
        del_y = abs(tile.y - self.base_position.y)

        entitytype = tile_data.building_type
        same_team = tile_data and tile_data.own_team

        if (del_x == 0 or del_y == 0) and max(del_x, del_y) == 2 and tile_data.environment == Environment.EMPTY:
            if tile_data.is_team_road() or entitytype in IGNORED_BUILDINGS:
                self.set_target(tile, 2, BotState.GOING_TO_TARGET)
        
        if max(del_x, del_y) == 2 and tile_data.environment == Environment.EMPTY:
            is_damaged = tile_data.own_team and self.ct.get_hp(tile_data.building_id) <= self.ct.get_max_hp(tile_data.building_id) - 4
            if is_damaged:
                self.potential_targets.append(tile)

            if entitytype in IGNORED_BUILDINGS or tile_data.is_team_road():
                self.potential_targets.append(tile)
            elif entitytype == EntityType.SPLITTER and same_team:
                # if self.ct.get_stored_resource(tile_data.building_id) == ResourceType.TITANIUM:
                #     target_pos = get_conveyor_target(tile, self.ct)
                #     target_entity = get_entity(target_pos, self.ct)
                #     print(f"target_entity: {target_entity} from barrier")
                #     if target_entity == EntityType.BARRIER or target_entity in IGNORED_BUILDINGS or target_entity == EntityType.ROAD:
                #         self.potential_targets.append(target_pos) 
                        
                if self.ct.get_stored_resource(tile_data.building_id) == ResourceType.RAW_AXIONITE:
                    target_pos = get_conveyor_target(tile, self.ct)
                    target_entity = get_entity(target_pos, self.ct)
                    print(f"target_entity: {target_entity}")
                    if target_entity == EntityType.BARRIER:
                        self.potential_targets.append(target_pos) 

    def update_map(self):
        self.potential_targets = []
        super().update_map()     
        print(self.potential_targets) 
        if self.potential_targets and self.current_state != BotState.GOING_TO_TARGET:
            target = min(self.potential_targets, key=lambda p: self.position.distance_squared(p))
            self.set_target(target, 0, BotState.GOING_TO_TARGET)

    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        del_x = abs(move_pos.x - self.position.x)
        del_y = abs(move_pos.y - self.position.y)
        if get_skibidi_distance(self.position, self.current_target_position) <= 1 and self.current_state == BotState.GOING_TO_TARGET:
            if self.ct.get_action_cooldown() == 0:
                self.reached_target()
            return

        elif del_x + del_y == 3:
            d = decide_splitter_direction(move_pos, self.base_position)
            if self.ct.can_build_splitter(move_pos, d):
                self.ct.build_splitter(move_pos, d)
        else:
            return super().build_road(move_pos, next_pos)
        return True
    
    def reached_target(self):
        print("Reached target")
        if self.current_state == BotState.WANDERING:
            return
        del_x = abs(self.current_target_position.x - self.base_position.x)
        del_y = abs(self.current_target_position.y - self.base_position.y)
        tile_data = self.get_from_pos(self.current_target_position)
        
        if not tile_data:
            return
        
        if self.ct.can_destroy(self.current_target_position) and tile_data.is_team_road():
            self.ct.destroy(self.current_target_position)
        
        if self.ct.can_fire(self.current_target_position) and tile_data.building_type == EntityType.ROAD and not tile_data.own_team:
            self.ct.fire(self.current_target_position)

        if self.current_target_position == self.position and self.current_state == BotState.GOING_TO_TARGET:
            self.move_to_adjacent()

        if del_x == del_y and del_x == 2:
            if self.ct.can_build_barrier(self.current_target_position):
                self.ct.build_barrier(self.current_target_position)
        elif del_x == 0 or del_y == 0:
            to_build = EntityType.BARRIER
            entity_cost = self.ct.get_barrier_cost()[0]
            e_type = self.get_from_pos(self.current_target_position).building_type
            if e_type == EntityType.BARRIER:
                to_build = EntityType.FOUNDRY
                entity_cost = self.ct.get_foundry_cost()[0]
            # elif e_type == EntityType.LAUNCHER:
            #     to_build = EntityType.FOUNDRY
            #     entity_cost = self.ct.get_foundry_cost()[0]
            elif e_type == EntityType.FOUNDRY:
                self.set_wandering()
                return
            print(f"Trying to build {to_build} at {self.current_target_position}")
            g_resource = self.ct.get_global_resources()[0]
            can_build = g_resource >= entity_cost and self.ct.get_action_cooldown() == 0
            if can_build and self.ct.can_destroy(self.current_target_position) and get_entity(self.current_target_position, self.ct) != to_build:
                self.ct.destroy(self.current_target_position)
            
            if self.ct.can_build(to_build, self.current_target_position):
                self.ct.build(to_build, self.current_target_position)
        elif max(del_x, del_y) == 2:
            d = decide_splitter_direction(self.current_target_position, self.base_position)
            
            print(self.current_target_position)
            if self.ct.can_build_splitter(self.current_target_position, d):
                self.ct.build_splitter(self.current_target_position, d)


        self.set_wandering()
    
    def nearest_unexplored(self):
        return self.base_position
    
    def set_wandering(self):
        self.set_target(self.base_position, 0, BotState.WANDERING)

"""                                                                                                                               
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@#-.                       .=#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%*+=-:    .    .   .  . . ..      .:-=+*%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@*=:           .    ....  .....  ..           .:=*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@*-.    .  .             ::::::..            .  .    .-*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@*:.  .  .    .          :#%*===+%#:            .   .    .:*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%=.    .                  =%+    .=%=                   .   .=%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%-.                        =%+=: :==%=.                        -%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@%-                         .+%#**+***%+.                         :#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@%-                            .:::::::.                            :#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@%:                                                                   :%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@=                           .......  ......                           =%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@*.                                                                     .+@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@*:                           ...:::::::::::...                           .*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@%:                   .-=************#*##*************+-.                   :%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@*.               :-=+**#%%%%%%%%%%%%%%%%%%%%%%%%%#%%%#**+=-.                +@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@%-             :===+**##%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#**++==:             =%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@#:          .-==+***##%%%%%%%%%%%%@@@@@@@@@@@@%%%%%%%%%%%##***+==-.          :#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@*.        .-==+***#***#%%%%%%%%%%%@@@@@@@@@@@%%%%%%%%%%%#*******++=-:        .+@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@=        :=+****+==--====+*##%%%%%%@@@@@@@@@%%%%%%##*+====--==++***+=:        -%@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@%:       -===::::::.....:::::=+**#%%%%%%%%%%%%%#*++=:::::....::::..:===-       :%@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@*:     .===::.....          .::-=**#%%%%%%%%%#**=-::.           .....:===.     .*@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@*.    .===:::-===-::..        .::=+**#*****#**+=-:.        ..::-===-:::===:     *@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@=    .=+=---===++**+=-::       .::=============::..      .:-=+**+++==---=+=.    =@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@=    -==-::===++***===-:::.     .::::-------:::..     ..:--===+***+===-:-==-    =@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@=   :=+=-::--=-:..                 .::-===-::.                 ..:----::-=+=:   =@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@=  :=++=:::::.                     .:-==++=-:.                     .:::::=++=.  =@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@=  :=++=::::    :+*==*+++:         .:=+*#*+=:.         :++++==*+:    ::::==+=:  =@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@=  -===-:..    -**:.....-*=:    ..::-=*%%%*=-::..    .=*=.....:+*-    .:::===-  =@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@%***#%%:  -==-:...   :===      :==--:::---==*#%@%#*==---:::====:      =+=:.  ...::==-  :%%#***%@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@%=.::=++-..-==-:::..:-==++++==++++===+++=+++**%%@%%**++==+++===++++==++**+=-::..::-==-..-++=::.-%@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@#.    .:::.-=======++=-::----::::::=+********#%%@%%#********+=-:::::----::-=++====-==-:.::.    .*@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@%:       ..-===+****+=-:.     .:=*#%%##*****#%%%@%%%#*****##%%#*=::     .:-=+*****===-..       :#@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@=    .:::.-===+**#%%%%%%%%###%%%%%%%##****#%%%@@@%%%##****#%%%%%%####%%%%%%%%#**+===-::::.    =@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@%-   ::::.:--=+*#%%%%%@@@@@@@%%%%%#*****#%%%%%@@@%%%%%#*****#%%%%%@@@@@@@@%%%%#*+==-:.::::   :%@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@%-  :::. :-==*#%%@@@@@@@@@@@%%%#**=+***%%%%@@@@@@@@%%%***++**#%%%%@@@@@@@@@@%%#*+=-: .:::  :%@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@%-..:.  :-=**#%%%@@@%%%%%%#**=-:=*#*##%%@@@@@@@@@@@%%%#*#*=:-=**#%%%%%@@@@%%%#**=-:  ::..=%@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@%=.::. :==++**##%%###***==-:..:*#%##%%%%%%%@@@%%%%%%%##%#*-..::==***####%##**++==:..::.-%@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@%-:-:::-=====+****+++==:.   :-+***+==+***********+==+***+-:   .:===++****+======:::-:-%@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@*-==-:-------======-::   .-==:::::::::===---===:::::::::==-:   ::-=======-----::-==:*@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@%=::=:::::::-==--::..   :-===::       .::::::::       .:===-:.  .:::-----:::::::-::=%@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@%=-:=: .:::::::::..   .:-====-::                     ::-===--:.    .:::::::::..:=:-=%@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@=--:   .::::::.    ..::---==-::::                 .:::-===--::..    .:::::..   :--=%@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@*=**:    .  .       :-=+===-::..                   ..:::===+=-:          ..   :**=*@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@%*#=:          ..  ::-----::..       ...    ..      ...:::----::  ..          :=#*%@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@*::.         .:....    ...   .    :===:::::===:.       ....    ...:.         .::*@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@%-          .:::.           ...::-==++++*++++==:::...  .        .:::..         :%@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@#:         ..::.       ......  . .....:::......    .....       .:::          :#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@*:          ..             .      ..     ..      .             ..          :*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@#:         ..           -=*+=+=-=**+-:-+**+==+=+*=-.          ..         :#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@#:         ..      ...:=**%%%%%%@@@%*%@@@%%%%%%#*=: .:      ...        :*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@%-          ..    .:---:.:+*%%%@@@@%%%@@@@%%%*+:.::--:.     .          -#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@%+          ..    .::====.  :=+*%%%%#%%%%*+=:  :-===-::.    .          =%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@*:                .:::-======-:  ...    ..  ::======-:::.                :*@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@#:  :               .:-::--=--=*****+=---=+*****=--==-::-:.              .:  :#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@%=...                  ::::::---:-=***##%%%##***=-:---::::::.                 .. =%@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@*-.                       .::::::::::::::-=====-::::::::::::::.                       .-*@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@%*:.:=-                        .:::::.:::::::::::::::::::::::::::.                        -=:.:*%@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@%#*:   ::                           ::::::...................:.::::::                           ::   :*#%%@@@@@@@@@@@@@@@
@%*=-:.       ..                             .:::::....             ...::::::.                             .       ..:-=*%@@@@@@@@
.....                                        .::::::..               ..::::::.                                         ....:+#%@@@
                                             .:::::::..             ...::::::.               .                               ..:=*
                             .               .::-::::::::..     ..:::::::::::.               .                                  .:
      .                     .     .           ..:-=======---:::---=======-:..           .     .                     .             
   .....                   ..     ..           .::-=========++==========-::.           ..     ..                    .....         
.:::.                      ..     .::.            .::-======++++=====--::.           .::.     ..                    . .::..       
:::.                       .      .::.              .::::::::::::::::..              .::.      .                       .:::..     
::...                     .:       ::.                    ........                   .::       ::                     . .:::::... 
: ..                      ..       .::.                                             .::.       ..                      .. ::::::..
 .. ...                  ::         ::.                                             .::         :.                   .. ..  ....:.
 ...                    .:.         .:.                                             .:.         .:.                    .... ..:::.
. ..                   .::           . .                                                         ::.                   ..  ...::::             
"""