from entity_behaviour.entity_base import *
from cambc import EntityType, ResourceType, Position
from utils.constants import _SENTINEL, PASSABLE
from utils.helper_functions import *
from utils.constants import *

# Entity types that block line of sight AND are valid targets for the gunner
BLOCKING_TARGETABLE = {EntityType.BUILDER_BOT, EntityType.SENTINEL, EntityType.BREACH, EntityType.GUNNER, 
                       EntityType.BARRIER}  # adjust to whatever your non-marker buildings are

class Gunner(EBase):
    def __init__(self, ct: Controller):
        super().__init__(ct)

    def run_tick(self, ct: Controller):
        print("Running tick")

        current_dir = ct.get_direction()
        my_pos = ct.get_position()

        def get_occupant_team(pos: Position):
            """Returns (entity_type, team) of whatever is on this tile, or (None, None)."""
            bot_id = ct.get_tile_builder_bot_id(pos)
            if bot_id:
                return ct.get_entity_type(bot_id), ct.get_team(bot_id)
            building_id = ct.get_tile_building_id(pos)
            if building_id:
                building_entity = ct.get_entity_type(building_id)
                if building_entity in IGNORED_BUILDINGS:
                    return None, None
                return building_entity, ct.get_team(building_id)
            return None, None

        def is_enemy(team):
            return team is not None and team != self.team

        # Use the API to get the full geometric pattern (handles √13 radius correctly)
        attackable_tiles = ct.get_nearby_tiles()

        # Group legal shots by the cardinal direction they lie in
        forward_targets = []   # (distance, pos)
        other_targets = {}     # Direction -> (distance, pos)

        for tile_pos in attackable_tiles:
            tile_dir = my_pos.direction_to(tile_pos)
            if not self.can_fire(tile_pos):
                print(f"Can't fire from {my_pos} to {tile_pos} direction {tile_dir}")
                continue

            entity_type, team = get_occupant_team(tile_pos)
            if not is_enemy(team):
                print(f"Not enemy team {tile_pos} entity {entity_type}")
                continue

            dist = get_skibidi_distance(my_pos, tile_pos)
            entry = (dist, tile_pos)
            print(f"Checking {tile_pos}, {entity_type}")

            if tile_dir == current_dir:
                forward_targets.append(entry)
            else:
                other_targets.setdefault(tile_dir, []).append(entry)

        print(forward_targets)
        print(other_targets)
        # Fire the closest legal enemy in our current facing direction
        if forward_targets:
            _, best_pos = min(forward_targets, key=lambda e: e[0])
            if ct.can_fire(best_pos):
                ct.fire(best_pos)
            return

        # No forward shot — rotate toward the direction with the closest reachable enemy
        if other_targets:
            best_dir = min_with_random_tiebreak(
                other_targets,
                key=lambda d: min(dist for dist, _ in other_targets[d])
            )
            if ct.can_rotate(best_dir):
                ct.rotate(best_dir)

    def can_fire(self, pos: Position):
        dx = pos.x - self.original_position.x
        dy = pos.y - self.original_position.y
        if dx == 0 or dy == 0:
            return True
        
        if abs(dx) == abs(dy):
            return True