from cambc import Controller, Position, EntityType, Team
from utils.constants import *
from typing import overload
import random

@overload
def is_in_bound(pos: Position, ct: Controller) -> bool:
    w = ct.get_map_width()
    h = ct.get_map_height()
    return is_in_bound(pos, w, h)

@overload
def is_in_bound(pos: Position, w: int, h: int) -> bool:
    return 0 <= pos.x < w and 0 <= pos.y < h

@overload
def is_in_bound(x: int, y: int, w: int, h: int) -> bool:
    return 0 <= x < w and 0 <= y < h

def is_in_bound(*args) -> bool:
    if len(args) == 4:
        x, y, w, h = args
    elif len(args) == 3:
        pos, w, h = args
        x, y = pos.x, pos.y
    else:
        pos, ct = args
        x, y = pos.x, pos.y
        w, h = ct.get_map_width(), ct.get_map_height()
    return 0 <= x < w and 0 <= y < h

def checkable_position(pos: Position, ct: Controller) -> bool:
    return ct.is_in_vision(pos) and is_in_bound(pos, ct)

def direction_to_delta(direction_type: DeltaTypes) -> list[tuple[int, int, float]]:
    match direction_type:
        case DeltaTypes.ALL:
            return ALL_DELTAS
        case DeltaTypes.CARDINAL:
            return CARDINAL_DELTAS
        case DeltaTypes.BRIDGE:
            return BRIDGE_DELTAS
        case DeltaTypes.DIAGONAL:
            return DIAGONAL_DELTAS

def is_team_road(pos: Position, ct: Controller) -> bool:
    building_id = ct.get_tile_building_id(pos)
    etype = ct.get_entity_type(building_id) if building_id else None
    return building_id and etype == EntityType.ROAD and ct.get_team(building_id) == ct.get_team()

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

def other_team(team: Team) -> Team:
    match team:
        case Team.A:
            Team.B
        case Team.B:
            Team.A

def check_for_entity(position: Position, ct: Controller, directions: list[Direction], entity: EntityType, team: Team) -> Position:
    for d in directions:
        check_pos = position.add(d)
        if not checkable_position(check_pos, ct):
            continue
        check_id = ct.get_tile_building_id(check_pos)
        check_entity = ct.get_entity_type(check_id) if check_id else None
        if check_entity == entity:
            if ct.get_team(check_id) == team:
                return check_pos
            
def get_positions_of_entities(position: Position, ct: Controller, radius: int, entity: EntityType, team: Team) -> Position:
    result = []
    for entity_id in ct.get_nearby_entities():
        if ct.get_position(entity_id).distance_squared(position) > radius:
            continue
        if ct.get_team(entity_id) == team and ct.get_entity_type(entity_id) == entity:
            result.append(ct.get_position(entity_id))
    
    return result

def check_for_env(ct: Controller, directions: list[Direction], env: Environment) -> Position:
    position = ct.get_position()
    for d in directions:
        check_pos = position.add(d)
        if not checkable_position(check_pos, ct):
            continue
        check_env = ct.get_tile_env(check_pos)
        if check_env == env:
            return check_pos

def get_entity(pos: Position, ct: Controller) -> EntityType | None:
    b_id = ct.get_tile_building_id(pos)
    return ct.get_entity_type(b_id) if b_id else None

def is_passable(pos: Position, ct: Controller) -> bool:
    if not checkable_position(pos, ct):
        return True
    b_entity = get_entity(pos, ct)
    env = ct.get_tile_env(pos)
    return env != Environment.WALL and (b_entity in IGNORED_BUILDINGS or b_entity in PASSABLE)

def destroyable(pos: Position, ct: Controller) -> bool:
    if not checkable_position(pos, ct):
        return False
    b_id = ct.get_tile_building_id(pos)

    return b_id and ct.get_entity_type(b_id) in DESTROYABLE_BUILDINGS and ct.get_team(b_id) == ct.get_team()

def is_exposed(pos: Position, ct: Controller) -> bool:
    if not pos:
        return False
    if not checkable_position(pos, ct):
        return False
    if get_entity(pos, ct) not in CONVEYORS:
        return False
    return check_for_entity(pos, ct, DIRECTIONS, EntityType.LAUNCHER, ct.get_team()) is None

def encode_coordinate(pos: Position) -> int:
    encoded = (pos.x << 6) | pos.y
    return encoded


def decode_coordinate(encoded: int) -> Position:
    x = encoded >> 6
    y = encoded & 0b111111
    return Position(x, y)

def get_skibidi_distance(pos1: Position, pos2: Position):
    return max(abs(pos1.x - pos2.x), abs(pos1.y - pos2.y))


def decide_splitter_direction(pos: Position, base_pos: Position):
    d = Direction.NORTH
    x_dif = pos.x - base_pos.x
    y_dif = pos.y - base_pos.y
    if abs(x_dif) > abs(y_dif):
        if y_dif > 0:
            d = Direction.NORTH
        else:
            d = Direction.SOUTH
    else:
        if x_dif < 0:
            d = Direction.EAST
        else:
            d = Direction.WEST
    return d

def get_conveyor_target(pos: Position, ct: Controller):
    building_id = ct.get_tile_building_id(pos)
    building_entity = get_entity(pos, ct)
    position = None
    match building_entity:
        case EntityType.CONVEYOR | EntityType.SPLITTER:
            d = ct.get_direction(building_id)
            position = pos.add(d)
        case EntityType.BRIDGE:
            position = ct.get_bridge_target(building_id)
        case _:
            return None
    
    return position
    
def limit_to_map(pos: Position, ct: Controller):
    def clamp_between(a, b, x):
        return max(min(b, x), a)
    return Position(clamp_between(0, ct.get_map_width() - 1, pos.x), clamp_between(0, ct.get_map_height() - 1), pos.y)

def get_connections(pos: Position, team: Team, ct: Controller, seen: list[int]=[]) -> set[EntityType]:
    if not checkable_position(pos): return set(EntityType.MARKER) # Could be connected

    building_id = ct.get_tile_building_id(pos)
    if building_id in seen: return set() # A loop has formed
    if building_id is None: return set(None)

    etype = ct.get_entity_type(building_id)
    seen.append(building_id)

    if etype in IGNORED_BUILDINGS:
        return set()

    match etype:
        case EntityType.CONVEYOR | EntityType.ARMOURED_CONVEYOR | EntityType.BRIDGE:
            check_pos = get_conveyor_target(pos, ct)
            return get_connections(check_pos, team, ct, seen)

        case EntityType.SPLITTER:
            face_direction = ct.get_direction(building_id)
            check_positions = [pos.add(d) for d in CARDINAL_DIRECTIONS if d != face_direction.opposite()]
            ret = set()
            for p in check_positions:
                ret = ret.union(get_connections(p, team, ct, seen))
            
            return ret
    
    if team != ct.get_team(building_id):
        return set()

    return set(etype)

def is_connected_to(pos: Position, target_type: EntityType, team: Team, ct: Controller) -> bool:
    connections = get_connections(pos, team, ct)
    if target_type in connections or EntityType.MARKER in connections:
        return True
    return False

def is_connected_to_turret(pos: Position, team: Team, ct: Controller) -> bool:
    connections = get_connections(pos, team, ct)
    return not TURRETS.isdisjoint(connections)

def is_directly_connected_to_turret(pos:Position, team: Team, ct: Controller) -> bool:
    c_target = get_conveyor_target(pos, ct)
    if not checkable_position(c_target, ct):
        return False
    turret_id = ct.get_tile_building_id(c_target)
    if turret_id:
        turret_type = ct.get_entity_type(turret_id)
        if turret_type in TURRETS and ct.get_team(turret_id) == team:
            return True

    return False 