from cambc import Controller, Environment, Position, EntityType, ResourceType
from entity_behaviour.bot import Bot
from utils.constants import CONVEYORS, BotState, DeltaTypes
from utils.helper_functions import *

class BaseBuilder(Bot):
    def __init__(self, ct: Controller):  
        self.potential_targets = []      
        super().__init__(ct)

    def update_tile(self, tile, building_id, bot_id):
        if not checkable_position(tile, self.ct):
            print(f"Something is weird for: {tile}")
            return
        if not self.ct.is_tile_passable(tile):
            self.set_from_pos(self.internal_map, tile, Environment.WALL)

        if self.current_state == BotState.GOING_TO_TARGET:
            print(self.current_target_position)
            return
        
        env = self.ct.get_tile_env(tile)
        del_x = abs(tile.x - self.base_position.x)
        del_y = abs(tile.y - self.base_position.y)

        entitytype = get_entity(tile, self.ct)
        same_team = building_id and self.ct.get_team(building_id) == self.team

        if (del_x == 0 or del_y == 0) and max(del_x, del_y) == 2 and env == Environment.EMPTY:
            if is_team_road(tile, self.ct) or entitytype in IGNORED_BUILDINGS:
                self.set_target(tile, 2, BotState.GOING_TO_TARGET)
        
        elif max(del_x, del_y) == 2 and env == Environment.EMPTY:
            if entitytype in IGNORED_BUILDINGS:
                self.potential_targets.append(tile)
            elif entitytype == EntityType.SPLITTER and same_team:
                if self.ct.get_stored_resource(building_id) == ResourceType.TITANIUM:
                    target_pos = get_conveyor_target(tile, self.ct)
                    target_entity = get_entity(target_pos, self.ct)
                    if target_entity == EntityType.BARRIER or target_entity in IGNORED_BUILDINGS or target_entity == EntityType.ROAD:
                        self.potential_targets.append(target_pos) 
                        
                elif self.ct.get_stored_resource(building_id) == ResourceType.RAW_AXIONITE:
                    target_pos = get_conveyor_target(tile, self.ct)
                    target_entity = get_entity(target_pos, self.ct)
                    if target_entity == EntityType.LAUNCHER and target_entity not in CONVEYORS:
                        self.potential_targets.append(target_pos) 

    def update_map(self):
        self.potential_targets = []
        super().update_map()      
        if self.potential_targets and self.current_state != BotState.GOING_TO_TARGET:
            target = min(self.potential_targets, key=lambda p: self.ct.get_position().distance_squared(p))
            self.set_target(target, 2, BotState.GOING_TO_TARGET)


    def build_road(self, move_pos: Position, next_pos: Position) -> bool:
        if get_skibidi_distance(move_pos, self.base_position) == 2:
            d = decide_splitter_direction(move_pos, self.base_position)
            if self.ct.can_build_splitter(move_pos, d):
                self.ct.build_splitter(move_pos, d)
        return True
    
    def run_flood_fill(self):
        return super().run_flood_fill()
    
    def reached_target(self):
        del_x = abs(self.current_target_position.x - self.base_position.x)
        del_y = abs(self.current_target_position.y - self.base_position.y)
        if self.ct.can_destroy(self.current_target_position) and is_team_road(self.current_target_position, self.ct):
            self.ct.destroy(self.current_target_position)
        
        if self.ct.can_fire(self.current_target_position) and get_entity(self.current_target_position, self.ct) == EntityType.ROAD:
            self.ct.fire(self.current_target_position)

        if del_x == del_y and del_x == 2:
            if self.ct.can_build_barrier(self.current_target_position):
                self.ct.build_barrier(self.current_target_position)
        elif del_x == 0 or del_y == 0:
            to_build = EntityType.BARRIER
            entity_cost = self.ct.get_barrier_cost()[0]
            e_type = get_entity(self.current_target_position, self.ct)
            if e_type == EntityType.BARRIER:
                to_build = EntityType.LAUNCHER
                entity_cost = self.ct.get_launcher_cost()[0]
            elif e_type == EntityType.LAUNCHER:
                to_build = EntityType.FOUNDRY
                entity_cost = self.ct.get_foundry_cost()[0]
            
            g_resource = self.ct.get_global_resources()[0]
            can_build = g_resource >= entity_cost and self.ct.get_action_cooldown() == 0
            if can_build and self.ct.can_destroy(self.current_target_position) and get_entity(self.current_target_position, self.ct) != to_build:
                self.ct.destroy(self.current_target_position)
            
            if self.ct.can_build(to_build, self.current_target_position):
                self.ct.build(to_build, self.current_target_position)
        elif max(del_x, del_y) == 2:
            d = decide_splitter_direction(self.current_target_position, self.base_position)
            if self.ct.can_build_splitter(self.current_target_position, d):
                self.ct.build_splitter(self.current_target_position, d)

        self.set_wandering()
    
    def nearest_unexplored(self):
        return self.base_position
    
    def set_wandering(self):
        self.set_target(self.ct.get_position(), 0, BotState.WANDERING)

"""                                                                                                                               
 :.::::::.-::::-:------:::::::.....:.::::.:::::::::::::::::..:-. ++-:---:-:----===-===+==++-=::-------:-:==-==  .......:. ...               
 :--:::::::-:-::.....:--.--:----:::-:-------------::::---------  %+========+-----------=-=-:=++===++===-====-** ..:...:.... .               
 .... : -:::::::::::::::::::::::::::---...........----...----:-. :*===---.:::-...:-.....  ...  ...:-=========*@  .      .. .                
 ..-:-..-::::::::::::       :::::::::.:::::::::::::..:::::..::-+  #=======+=====-+--=-=-====++===--:.:------**=                     ....::. 
 -----.:.-------------=------:::--::::::::---------------------.. %=-==-===-===--=================+++=---===*   ..  ......:::::..:::::::.:- 
 ::....::... .....:::.:.:::::.::.:-.----:-.....:..::.:::::::.:::  %=-=====-====---==---======-====--===-=-:+*  ........--..:::::.           
 .:.----:::-.:::::... :-:....:.             ...::-::-: . ...-.:   #====---==--==-==+++++++===============--#   :.:--:::::::.::.             
 .................:::.   ::..   -@@@@@@@@@=   ............:::.  -%*-====--:-::::::::      .---=====--====-=#   .:..::::::...:          .    
 ...::::::::..........::...   @@@         @@@  .: .....::.    -#*+=---=--=====++==+=+++++++==-::.:-==-=-==#. :::::..:-.:.::...      ... .-. 
 :::::::::::::::::..:::.... .@@    .. ..    @@: :. .          #+:--======+==+++=+=+=================:-----#    -::-::::::          .  -:.:. 
          ..:....::.: ....  .@@  . .:::...   @@ .:.   %@@@@@@#*@*=-:=-==--..:::----++===-=-====+==-===-=--%    .                    :.. ... 
 ...........  .. .:::...:::. @@@.     ..... +@+ :   @@@+        -#++-: ...--:.          ..::-:---==-======%. .                   -::..::::: 
 ....     ......   .           .#@@@@+.   : @.    @@#    ..::-.  @:--=++++====*++++*++*+==:.. .. .:--:-=*@@                    :.. .:.....  
 ::::.-.-........    :%@@@@@.          %-:: #@@@@%    ........   @-+--:---==--====-=========++==+===::=*+   ...         ..:::..:.:.:-:::::: 
 ::.::. .:::::::  @@@@-      #@@@@@@@@@+                      %@:%#+++++-:::.---===---=--=-==--=====+##   -::..::::---:.::.-::-:::::.---.-- 
 ...:::::.:::... %@+   :=:-..          - +%%+@%  .%@@@@@@@@@@+:    #@@#+++*.:=---=-----------=--===+#+  :..:-::::..:..:-.:..:-------::::::: 
 :-::::.::::.-:- +@   ---:          .. :*=  =@@ @.              ..    @@@@@%*---==----==--=+==--+*%%   ..::::--.-------::----:::::::::::::: 
 :.:-::::::::-:.::@@@+.. =@@@@@@@@@*  +=. -:.    +@@@@@@@@@@@@-   ==      :@@#+--=----===*##%%%@@    :.:::.-----::::::::::::::::::::::::::: 
 .:............::    .-==          -@ = . . *##:              *@#.==-=:::.    +===--+*%@+.        .:..--=-:-....---------:::::::::::::::::: 
 ::::.::::::::....:..   . .   #@@@%.  ... @*   +@:  ...:: ::   %@    ..::-...  =====#.    ..::::.::::... ..:----::::::::.---------------::: 
    -:::: .-:::::.:::::::.  @@.    .::::: @  :. @@=   .:     =@@# ...::.    . @%#+++:  : -:::::::..:.:::...................-:::::::::::::=- 
 ...  ..:    .     -...-. .@%   ...       @@ .   =@@@-    :@@@@  .::::: .-@@*:.  =@@@ - ..- ... ...:::..:::::::.......:.....  ...........   
 .:............-.:   :.   .@@   ....:::.. :@ .:-.   =@@@@@@      ..: :-=+     .      .@-.:....:-:::-..-::::::::--::::---------::--::::::::. 
 .....:.:::::....:...:....  @@@           @@ . .              ...: -#@@  *@@@@@ =: *   .- :-::.  ...  . ......    ..           .   .     -: 
 :-.:::.....:.:-::::: ::..    @@@@@@@@@@@@    ...:.:.::::......=*-      #      @@=-+#   .  .  -::. ......................................   
         ...      . .   .....               ...:.......   .::-*-  @@@@@ %@@@@@@ .@.--%    . ..   ....................... .................. 
 ....:::.::: .....-::::::  ...           .....:  .    .....  #  @@@@@  @@@@@@@@  *=--+%     . ..  .::.......................... ........... 
 ...:        .. .      :%%=:...........::      .  .....    ..@ @@@    @@%@   -@  *--::=*#    .  ...        ...:............................ 
 .: .....:.....::    -+#  *-- .... .. .  ......... ..........@ @@@@@ @@##@@@@@  @=:-----=%    .. ........:-=---:+=-:.:................... : 
 ....:: . .+=-:  :=##+: .@  .......:: ............ ..-===-:..@  @@@@ #@@@@@@@  **=:------+%     . .....:              ..................... 
  .-+* -.+@  ==##@     *=  =:+*%@@=:---. ......... .-     .%@@* %  -#   +    =+:-+@@@*=:--:+%    :.                  ...................... 
 %@@   @%:  *# .    .     @@@+    =+-  :........ ...-             ::=#%@@@@@@@@@@@   =-::---+%     ..... :          ..:.....: :..:......... 
      @   =@#:        #+ @          .- . ..  . . .. -      @@@@@@*=-=:.          .@@@=-::--:-=#.           . .-:::--:. .  .::.. .  . :..... 
  +:      -    . : :.+    -=:   . *  - .. .... . ...-==-@  #-::-:---:-+@@@@@@@@@@#=-::::---:--=+#            . ...  .:.....   :::  ..: .. . 
 -.  =@@ ++***:.:+%*#   =:=*-:   = -++:..::.:. ...... :=  *+--::--::::::::::.-:-----==---::-----+@.  .       .                     ..   .   
  :%.           :             : %  %-..  ..   ..... .:   @*-=:-++----------=-==--:-...------:=:-:=%.   .     ..              .      .:..... 
 -@   :@@@@@ @@   @*@@  @@@@  + *  - .::.......... ::  **+--=-++.-=::::---=::::--::-:.:----=++=:::-*@         ..       #***            .... 
       @   # #--  %  + %..-%  =-. @=:::..:::----:-=   #+-=.:-=    =---::---:---:-=--+--=--== =*=::--+@   .....  ......     .::::....        
       @   + @.. :++ . *  .=  ++ ::                 %%+=--===+#@%*+------:::::::---==++---=+   ======*@       .                    ........ 
 -     @:.=* *.- +=#      .+  :. @         ::::   @#----:--:::-:..----:=-====------== .+---=*#+-------+@   ....:-==++++**##***++####%%@@@@@ 
 =     .:    .   #%=       =    :@@@@@@#+=.     *%=:--:::=-:-::----.::--------------+* -+:--------:----+%                                   
       .-    ::. :@--=-                        @%+==-:--=-::--.----:-:---------------=* :*--------:-----*+ .+#%%%*+=:      :*%@@@@@@@@@@@@@ 
       :-  .               =#@@@@@@@@@   :+%.=@**: *--------=:-----:-:::--------------+*  *=---------:-:-%#       +@@@@@@@@@@@+             
       =*     -@@@@@@@@@@+     :#@@**@@@*    %-=   +:-.:-----:---::-:==----------------+#  #=------------+#.                                
 .      =            -+%#@@@*            .  @==+#%#+-----:-:----:--------=#@%*=---------+=  #=-----------=#..*@@@%=                  @@@@@@ 
 :      :         @@@-             =@@@@@* +%:.::---:---=-=--::-----------    =---------=+*  *+---::---:--=@             @@@@@@@@@@@@*-:::: 
        -:-:         +=@@@@@@@@@@@@        @#:.:--+%@@@@+-=:-------------=#+.-=-:---------+*  #=-------:--:@           @@@++++=:::::::::::- 
         ::+%.                             :@@@@@#% ..  %--------:--------==+=--------------#  #*=---------%:        @@#:::...::::::::.:::: 
                                  ..             -@     %*--:---:=:-----------------:---:=+%@@@ #*------:-=*+.@@@@@@@#-=+=-:::::::::...:.:: 
 #+-==**##%%#%%%%%#@@@@@@      .=.  .*@@=  @@     @@#   @#+-=#@@@@@@@@@@@@@@@@@@@@@@@@*::-=-     *@*----+%@@= @@@@@+===+  -.::.:........... 
 ++*#*++++=====**##*+++@@@@@@@          @* @  :.+         @@@-                         .@=      @  #*=--=   @      @@@@@@@#-=---:-:-:::::-: 
                     =-               .*:=  @        .+#=                         =%@@@**%@@@@@@@@  *%+-+#*@@ :=**        *@@@@@@@@@@@@@@@@ 
 @@@@@@@@@@@@@@@@@@@                         @@*#@@-         ..  :*%*##+ @@@@@@@@@@@#*+=+=======+%@#  +@@@@#        =#@@#:                  
                                                                .                                                                           
"""