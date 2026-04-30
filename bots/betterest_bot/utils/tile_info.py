from cambc import *

from utils.constants import DESTROYABLE_BUILDINGS, PASSABLE

WALL = {Environment.WALL}
class TileData:
    __slots__ = ("position", "environment", "building_id", "building_type", "bot_id", "bot_team", "covered_by_enemy", "own_team")
    def __init__(
        self, position: Position, env: Environment, b_id: int | None=None, 
        b_type: EntityType | None=None, b_team: bool | None=None, 
        bot_id: int | None=None, bot_team: Team | None=None
    ):
        self.position = position
        self.environment = env
        self.building_id = b_id
        self.building_type = b_type
        self.bot_id = bot_id
        self.bot_team = bot_team
        self.covered_by_enemy = False
        self.own_team = b_team
    
    def passable(self, ct: Controller, walls=WALL):
        if self.bot_id and not ct.is_in_vision(self.position):
            self.bot_id = None
            self.bot_team = None
        return (
            self.environment not in walls and
            self.building_type in PASSABLE and
            self.bot_id is None and
            not self.covered_by_enemy and 
            not (self.building_type == EntityType.CORE and not self.own_team)
        )
    
    def is_team_road(self) -> bool:
        return self.building_type == EntityType.ROAD and self.own_team
    
    def is_team_bot(self, id) -> bool:
        return id != self.bot_id and self.bot_team
    
    def destroyable(self) -> bool:
        return self.building_type == EntityType.BARRIER and self.own_team
