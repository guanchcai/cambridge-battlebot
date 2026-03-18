import random
import math
import heapq
from cambc import Controller, Direction, EntityType, Environment, Position
from path_finder import flood_fill, get_cardinal

# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]
CARDINAL_DIRECTIONS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]

class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.internal_map = None
        self.walking_back = False
        self.original_pos = None
        self.walking_back_first = False
        self.bridge_builder = False
        self.current_target_pos = None

    def run(self, ct: Controller) -> None:
        if (not self.internal_map):
            self.internal_map = [[None] * ct.get_map_height() for _ in range(ct.get_map_width())]

        if (not self.original_pos):
            self.original_pos = ct.get_position()
        
        if (self.current_target_pos):
            ct.draw_indicator_line(ct.get_position(), self.current_target_pos, 0, 0, 1)

        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if self.num_spawned == 0:
                marker_pos = ct.get_position().add(Direction.NORTH).add(Direction.NORTH)
                if ct.can_place_marker(marker_pos):
                    ct.place_marker(marker_pos, 6769420)
                    
                spawn_pos = ct.get_position().add(Direction.NORTH)
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
                return
            if self.num_spawned * 500 <= ct.get_global_resources()[0] and self.num_spawned < 30:
                # if we haven't spawned 3 builder bots yet, try to spawn one on a random tile
                spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                if spawn_pos != Direction.NORTH:
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1
        elif etype == EntityType.BUILDER_BOT:
            pos = ct.get_position()

            # Bridge builder script, can be ignored
            for id in ct.get_nearby_buildings():
                if ct.get_entity_type(id) == EntityType.MARKER and ct.get_team(id) == ct.get_team() and ct.get_marker_value(id) == 6769420:
                    ct.destroy(ct.get_position(id))
                    self.bridge_builder = True
                    self.original_pos = self.original_pos.add(Direction.SOUTH)

            if (self.bridge_builder):
                build_bridges(ct, self.original_pos)
                return

            if (self.walking_back):
                if (self.original_pos == pos): 
                    self.walking_back = False
                    return
                else:
                    buildings_nearby = ct.get_nearby_buildings(9)
                    bridges_nearby = list(filter(lambda b: ct.get_entity_type(b) == EntityType.BRIDGE , buildings_nearby))
                    
                    if len(bridges_nearby) >= 3:
                        bridge_id = random.choice(bridges_nearby)
                        if ct.get_global_resources()[0] >= ct.get_bridge_cost()[0]:
                            if ct.can_destroy(pos):
                                self.walking_back = False
                                ct.destroy(pos)
                                if ct.can_build_bridge(pos, ct.get_position(bridge_id)):
                                    ct.build_bridge(pos, ct.get_position(bridge_id))
                                return


                distance_map = flood_fill(self.internal_map, self.original_pos, ct.get_position())
                decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(d), ct)]
                chosen = min(decisions, key=lambda d: get_from_dir(distance_map, pos, d))
                
                if (self.walking_back_first):
                    self.walking_back_first = False
                    if ct.can_destroy(pos):
                        ct.destroy(pos)
                        ct.build_conveyor(pos, chosen)
                        return
                
                next_decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(chosen).add(d), ct)]
                next_chosen = min(next_decisions, key=lambda d: get_from_dir(distance_map, pos.add(chosen), d))
                move_pos = pos.add(chosen)

                if (ct.can_build_conveyor(move_pos, next_chosen)):
                    ct.build_conveyor(move_pos, next_chosen)
                elif ct.can_destroy(move_pos):
                    if ct.get_entity_type(ct.get_tile_building_id(move_pos)) != EntityType.ROAD:
                        self.walking_back = False
                        return
                    ct.destroy(move_pos)
                    if ct.can_build_conveyor(move_pos, next_chosen):
                        ct.build_conveyor(move_pos, next_chosen)
                if ct.can_move(chosen):
                    ct.move(chosen)
                return
            
            # Check if we have reached an ore site
            for d in CARDINAL_DIRECTIONS:
                check_pos = pos.add(d)
                if not is_in_bound(check_pos, ct):
                    continue
                check_id = ct.get_tile_building_id(check_pos)
                if ct.can_build_harvester(check_pos) or (check_id and ct.get_entity_type(check_id) == EntityType.HARVESTER and ct.get_team(check_id) != ct.get_team()):
                    if (ct.can_build_harvester(check_pos)):
                        ct.build_harvester(check_pos)
                    self.walking_back = True
                    self.walking_back_first = True
                    return

            # Updating the map
            for tile in ct.get_nearby_tiles():
                self.internal_map[tile.x][tile.y] = ct.get_tile_env(tile)

            # Walking to the ore site
            for i, r in enumerate(self.internal_map):
                for j, t in enumerate(r):
                    if t == Environment.ORE_TITANIUM and ct.is_in_vision(Position(i, j)) and ct.get_tile_building_id(Position(i, j)) == None:
                        distance_map = flood_fill(self.internal_map, Position(i, j), pos)
                        decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(d), ct)]
                        chosen = min(decisions, key=lambda d: get_from_dir(distance_map, pos, d))
                        move_pos = pos.add(chosen)
                        if ct.can_build_road(move_pos) and ct.get_tile_env(move_pos) == Environment.EMPTY:
                            ct.build_road(move_pos)
                        if ct.can_move(chosen) and ct.get_tile_env(move_pos) == Environment.EMPTY:
                            ct.move(chosen)
                        else:
                            self._pick_random(ct)
                        return
                    
            # Move randomly
            self._random_movement(ct)

    def _random_movement(self, ct: Controller):
        def select_none():
            candidates = []
            for x in range(ct.get_map_width()):
                for y in range(ct.get_map_height()):
                    if self.internal_map[x][y] == None:
                        candidates.append(Position(x, y))
            return random.choice(candidates) if len(candidates) > 0 else None

        pos = ct.get_position()
        if self.current_target_pos:
            if (self.internal_map[self.current_target_pos.x][self.current_target_pos.y] != None):
                self.current_target_pos = select_none()
                return

            distance_map = flood_fill(self.internal_map, self.current_target_pos, pos)
            decisions = [d for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(d), ct)]
            chosen = min(decisions, key=lambda d: get_from_dir(distance_map, pos, d))
            move_pos = pos.add(chosen)
            print([get_from_dir(distance_map, pos, d) for d in CARDINAL_DIRECTIONS if is_in_bound(pos.add(d), ct)])
            if ct.can_build_road(move_pos) and ct.get_tile_env(move_pos) == Environment.EMPTY:
                ct.build_road(move_pos)
            if ct.can_move(chosen):
                ct.move(chosen)
            else:
                self._pick_random(ct)
            return
        
        self.current_target_pos = select_none()
        if not self.current_target_pos:
            # Explored all areas
            self._pick_random(ct)
    
    
    def _pick_random(self, ct: Controller):
        print("Picking random!")
        move_dir = random.choice(DIRECTIONS)
        move_pos = ct.get_position().add(move_dir)
        if ct.can_build_road(move_pos):
            ct.build_road(move_pos)
        if ct.can_move(move_dir):
            ct.move(move_dir)


def is_in_bound(pos: Position, ct: Controller):
    return pos.x in range(ct.get_map_width()) and pos.y in range(ct.get_map_height())

def get_from_dir(map: list[list], pos: Position, dir: Direction):
    p1 = pos.add(dir)
    val = map[p1.x][p1.y]
    return val if val != None else math.inf

def build_bridges(ct: Controller, foundary_pos: Position):
    move_dir = random.choice(DIRECTIONS)
    move_pos = ct.get_position().add(move_dir)
    if ct.can_move(move_dir) and move_pos.distance_squared(foundary_pos) <= 9:
        ct.move(move_dir)
    
    for d in DIRECTIONS:
        bridge_pos = ct.get_position().add(d)
        if ct.can_build_bridge(bridge_pos, foundary_pos):
            ct.build_bridge(bridge_pos, foundary_pos)
            return
        
        if not is_in_bound(bridge_pos, ct):
            return
        
        tile_id = ct.get_tile_building_id(bridge_pos)
        if tile_id and ct.get_entity_type(tile_id) != EntityType.BRIDGE and ct.get_position(tile_id).distance_squared(foundary_pos) <= 9:
            if ct.can_destroy(bridge_pos):
                ct.destroy(bridge_pos)
            if ct.can_build_bridge(bridge_pos, foundary_pos):
                ct.build_bridge(bridge_pos, foundary_pos)
                return

    