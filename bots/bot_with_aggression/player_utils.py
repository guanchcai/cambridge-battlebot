import random
import math
from cambc import Controller, Direction, EntityType, Environment, Position, ResourceType

# non-centre directions
DIRECTIONS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST, Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST]
CARDINAL_DIRECTIONS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
DIAGONAL_DIRECTIONS = [Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST]
PASSABLE = [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ROAD, EntityType.ARMOURED_CONVEYOR, EntityType.BUILDER_BOT, EntityType.CORE, EntityType.MARKER, EntityType.SPLITTER]
VALUABLE_ENEMY_ENTITIES = [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.FOUNDRY, EntityType.BUILDER_BOT, EntityType.CORE, EntityType.GUNNER, EntityType.SENTINEL]
MINEABLE = [Environment.ORE_TITANIUM]
CONVEYORS = {EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER}
STUCK_THRESHHOLD = 3

DIR_TO_DELTA_DICT = {
    Direction.NORTH: Position(0, -1),
    Direction.SOUTH: Position(0, 1),
    Direction.EAST: Position(1, 0),
    Direction.WEST: Position(-1, 0),
}

OFFSETS = [(dx, dy) for dx in range(-1, 2) for dy in range(-1, 2)]

def is_in_bound(pos: Position, ct: Controller):
    return pos.x in range(ct.get_map_width()) and pos.y in range(ct.get_map_height())

def get_from_dir(map: list[Environment | None], pos: Position, dir: Direction, w: int):
    p1 = pos.add(dir)
    val = get_from_pos(map, p1, w)
    return val if val is not None else math.inf

def get_from_pos(map: list[Environment | None], pos, w: int):
    if isinstance(pos, Position):
        return map[pos.x + pos.y * w]
    elif isinstance(pos, tuple):
        return map[pos[0] + pos[1] * w]
    
def set_from_pos(map: list, pos: Position, v, w: int):
    map[pos.x + pos.y * w] = v 


def min_with_random_tiebreak(iterable, key=(lambda x: x)):
    it = iter(iterable)
    try:
        first = next(it)
    except StopIteration:
        return None

    candidates = [first]
    min_key = key(first)

    for x in it:
        k = key(x)
        if k < min_key:
            min_key = k
            candidates = [x]
        elif k == min_key:
            candidates.append(x)

    return random.choice(candidates)


def clamp(pos1: Position, pos2: Position) -> Direction:
    dx = pos2.x - pos1.x
    dy = pos2.y - pos1.y

    if abs(dx) >= abs(dy):
        return Direction.EAST if dx > 0 else Direction.WEST
    return Direction.SOUTH if dy > 0 else Direction.NORTH


def direction_to_delta(direction: Direction) -> Position:
    return DIR_TO_DELTA_DICT[direction]


def connected_to(pos: Position, building_id: int, target_building: EntityType, other_team: bool, ct: Controller):
    if not is_in_bound(pos, ct) or not ct.is_in_vision(pos): return False
    if ct.get_entity_type(building_id) == target_building and (ct.get_team(building_id) != ct.get_team()) == other_team:
        return True
    etype = ct.get_entity_type(building_id)

    match etype:
        case EntityType.CONVEYOR | EntityType.ARMOURED_CONVEYOR:
            check_pos = pos.add(ct.get_direction(building_id))
            if not is_in_bound(check_pos, ct) or not ct.is_in_vision(check_pos): return False
            check_id = ct.get_tile_building_id(check_pos)
            return check_id and connected_to(check_pos, check_id, target_building, other_team, ct)

        case EntityType.BRIDGE:
            check_pos = ct.get_bridge_target(building_id)
            if not is_in_bound(check_pos, ct) or not ct.is_in_vision(check_pos): return False
            check_id = ct.get_tile_building_id(check_pos)
            return check_id and connected_to(check_pos, check_id, target_building, other_team, ct)

        case EntityType.SPLITTER:
            check_positions = [pos.add(d) for d in CARDINAL_DIRECTIONS]
            tile_buildings = [ct.get_tile_building_id(p) for p in check_positions if ct.is_in_vision(p) and is_in_bound(p, ct)]
            for building_id in tile_buildings:
                if building_id and (ct.get_entity_type(building_id) == target_building and (ct.get_team(building_id) != ct.get_team()) == other_team):
                    return True
    return False

def limit(p: Position, ct: Controller):
    return Position(
        max(0, min(p.x, ct.get_map_width() - 1)),
        max(0, min(p.y, ct.get_map_height() - 1))
    )

def check_for_entity(p: Position, directions: list[Direction], entity: EntityType, ct: Controller, team = None) -> Position | None:
    for check_dir in directions:
        check_pos = p.add(check_dir)
        if not is_in_bound(check_pos, ct) or not ct.is_in_vision(check_pos):
            continue
        building_id = ct.get_tile_building_id(check_pos)
        if building_id and ct.get_entity_type(building_id) == entity and ((ct.get_team(building_id) == team) or (team is None)):
            return check_pos
    return 

def get_skibidi_distance(p1: Position, p2: Position):
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)
