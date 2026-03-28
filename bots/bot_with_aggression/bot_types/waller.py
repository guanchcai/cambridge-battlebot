from bot_types.bot import Bot, BOT_STATE
from path_finder_two import flood_fill
from player_utils import *

class Waller(Bot):
    def __init__(self, ct: Controller):
        super().__init__(ct)

    def _initialisation(self, ct):
        return super()._initialisation(ct)
    
    def _set_wandering(self):
        super()._set_wandering()
    
    def _set_internal_map(self, position):
        super()._set_internal_map(position)
    
    def _move_to_pos(self, ct: Controller):
        position = ct.get_position()
        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            fdist = get_fanum_tax_distance(self.current_target_pos, position)
            building_id = ct.get_tile_building_id(self.current_target_pos) if ct.is_in_vision(self.current_target_pos) else None
            bot_id = ct.get_tile_builder_bot_id(self.current_target_pos) if ct.is_in_vision(self.current_target_pos) else None
            
            corner = None
            for d in CARDINAL_DIRECTIONS:
                check_pos = self.current_target_pos.add(d)
                if not is_in_bound(check_pos, ct) or not ct.is_in_vision(check_pos):
                    continue
                b_id = ct.get_tile_building_id(check_pos)
                if b_id and ct.get_entity_type(b_id) in CONVEYORS:
                    for diag in get_adjacent_diagonal(d):
                        diag_pos = self.current_target_pos.add(diag)
                        if not is_in_bound(diag_pos, ct) or not ct.is_in_vision(diag_pos):
                            continue
                        diag_b_id = ct.get_tile_building_id(diag_pos)
                        if diag_b_id is None or ct.get_entity_type(diag_b_id) not in CONVEYORS:
                            corner = check_pos
                            break
                if corner is not None:
                    break
            if (bot_id and bot_id != ct.get_id()) or (building_id and ct.get_entity_type(building_id) != EntityType.ROAD):
                self._set_wandering()
                print("Already has a wall there")
                return
            
            if fdist == 0:
                if (
                    building_id and 
                    ct.get_team(building_id) != ct.get_team() and
                    ct.can_fire(self.current_target_pos)
                ):
                    ct.fire(self.current_target_pos)
                
                building_id = ct.get_tile_building_id(self.current_target_pos)
                if (
                    building_id is None or 
                    (
                        ct.get_entity_type(building_id) == EntityType.ROAD and 
                        ct.get_team(building_id) == ct.get_team() and 
                        ct.get_global_resources()[0] >= (ct.get_launcher_cost()[0] if corner else ct.get_barrier_cost()[0]) 
                    )
                ):
                    self._pick_random(ct)
                    return
            elif fdist == 1 and (building_id is None or ct.get_team(building_id) == ct.get_team()):
                can_afford = ct.get_action_cooldown() == 0 and (
                    ct.get_global_resources()[0] >= ct.get_launcher_cost()[0] if corner is not None else ct.get_global_resources()[0] >= ct.get_barrier_cost()[0]
                )

                
                if can_afford:
                    if ct.can_destroy(self.current_target_pos):
                        ct.destroy(self.current_target_pos)
                    
                    if corner is not None:
                        if ct.can_build_launcher(self.current_target_pos):
                            if check_for_entity(corner, DIRECTIONS, EntityType.LAUNCHER, ct, ct.get_team()):
                                ct.build_barrier(self.current_target_pos)
                            else:
                                ct.build_launcher(self.current_target_pos)
                            self._set_wandering()
                    elif ct.can_build_barrier(self.current_target_pos):
                        ct.build_barrier(self.current_target_pos)
                        self._set_wandering()
                    return
        
        super()._move_to_pos(ct, DIRECTIONS)

    def _build_road(self, ct: Controller, move_pos):
        print(f"Trying to build road at position: {move_pos}")
        if ct.can_build_road(move_pos):
            ct.build_road(move_pos)
    
    def _update_tile(self, tile, building_id, ct):
        if building_id and self.current_state == BOT_STATE.WANDERING and ct.get_team(building_id) == ct.get_team():
            if ct.get_entity_type(building_id) in [EntityType.HARVESTER, EntityType.BRIDGE, EntityType.CONVEYOR]:
                for d in CARDINAL_DIRECTIONS:
                    check_pos = tile.add(d)
                    if not (is_in_bound(check_pos, ct) and ct.is_in_vision(check_pos)) or ct.get_tile_env(check_pos) == Environment.WALL:
                        continue
                    check_id = ct.get_tile_building_id(check_pos)
                    bot_id = ct.get_tile_builder_bot_id(check_pos)
                    if bot_id is None and (check_id is None or ct.get_entity_type(check_id) == EntityType.ROAD):
                        self.current_target_pos = check_pos
                        self.target_distance_squared = 0
                        self.current_state = BOT_STATE.GOING_TO_TARGET
                        self.distance_map = None
                        return                        

    def _find_target(self, ct):
        self.current_state = BOT_STATE.WANDERING
        self.target_distance_squared = 16
        return self._nearest_unexplored(ct.get_position(), ct)
    
    def _nearest_unexplored(self, pos, ct: Controller):
        allowed_range = math.floor(5 * (ct.get_current_round() / 200 + 1))
        return limit(
            Position(self.original_pos.x + random.randint(-allowed_range, allowed_range), 
                     self.original_pos.y + random.randint(-allowed_range, allowed_range)),
            ct
        )

    def _read_markers(self, val, marker_pos):
        pass

    def _hit_wall(self, wall_pos, ct):
        print("I hit a wall!")
        print(wall_pos)
        bot_id = ct.get_tile_builder_bot_id(wall_pos)
        if bot_id:
            self._pick_random(ct)
            self.distance_map = None
            return
        
        self.distance_map = None
        

    def _target_reached(self, ct):
        if self.current_state == BOT_STATE.GOING_TO_TARGET:
            return
        self.current_target_pos = self._find_target(ct)