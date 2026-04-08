from cambc import *

from utils.constants import DESTROYABLE_BUILDINGS, PASSABLE

class TileData:
    __slots__ = ("environment", "building_id", "building_type", "building_team", "bot_id", "bot_team", "covered_by_enemy")
    def __init__(
        self, env: Environment, b_id: int | None=None, 
        b_type: EntityType | None=None, b_team: Team | None=None, 
        bot_id: int | None=None, bot_team: Team | None=None
    ):
        self.environment = env
        self.bot_id = b_id
        self.building_type = b_type
        self.bot_id = bot_id
        self.building_team = b_team
        self.bot_team = bot_team
        self.covered_by_enemy = False
    
    def passable(self):
        return (
            self.environment != Environment.WALL and
            self.building_type in PASSABLE and
            self.bot_id is None
        )
    
    def is_team_road(self, team: Team) -> bool:
        return self.building_type == EntityType.ROAD and self.building_team == team
    
    def destroyable(self, team: Team) -> bool:
        return self.building_type in DESTROYABLE_BUILDINGS and self.building_team == team
