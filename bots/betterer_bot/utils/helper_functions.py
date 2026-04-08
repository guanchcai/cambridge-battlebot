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
            return Team.B
        case Team.B:
            return Team.A

def get_entity(pos: Position, ct: Controller) -> EntityType | None:
    b_id = ct.get_tile_building_id(pos)
    return ct.get_entity_type(b_id) if b_id else None

def encode_coordinate(pos: Position, sym1: bool, sym2: bool, sym3: bool) -> int:
    encoded = (sym1 << 14) | (sym2 << 13) | (sym3 << 12) | (pos.x << 6) | pos.y
    return encoded

def decode_coordinate(encoded: int) -> tuple[Position, bool, bool, bool]:
    sym1 = bool((encoded >> 14) & 1)
    sym2 = bool((encoded >> 13) & 1)
    sym3 = bool((encoded >> 12) & 1)
    x = (encoded >> 6) & 0b111111
    y = encoded & 0b111111
    return Position(x, y), sym1, sym2, sym3

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
        case EntityType.CONVEYOR | EntityType.ARMOURED_CONVEYOR | EntityType.SPLITTER:
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
    return Position(clamp_between(0, ct.get_map_width() - 1, pos.x), clamp_between(0, ct.get_map_height() - 1, pos.y))
