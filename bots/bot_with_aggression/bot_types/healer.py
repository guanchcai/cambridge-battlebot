from bot_types.bot import Bot, BOT_STATE
from path_finder_two import flood_fill
from player_utils import *

class Healer(Bot):
    def __init__(self, ct):
        super().__init__(ct)

    def _initialisation(self, ct):
        return super()._initialisation(ct)
    
    def _set_wandering(self):
        return super()._set_wandering()
    
    def _set_internal_map(self, position):
        return super()._set_internal_map(position)
    
    def _move_to_pos(self, ct, cardinal=False):
        pass

    def _build_road(self, ct, move_pos):
        return super()._build_road(ct, move_pos)
    
    def _read_markers(self, val, marker_pos):
        return super()._read_markers(val, marker_pos)
    
    def _find_target(self, ct):
        return super()._find_target(ct)
    
    def _hit_wall(self, wall_pos, ct):
        return super()._hit_wall(wall_pos, ct)
    
    def _update_tile(self, tile, building_id, ct):
        return super()._update_tile(tile, building_id, ct)
    
    def _target_reached(self, ct):
        return super()._target_reached(ct)