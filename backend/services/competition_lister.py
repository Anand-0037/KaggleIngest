
import asyncio
from typing import List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from kaggle.api.kaggle_api_extended import KaggleApi

from backend.logger import get_logger
from backend.services.kaggle_service import KaggleService

logger = get_logger(__name__)

@dataclass
class CompetitionMetadata:
    slug: str
    title: str
    description: str
    deadline: Optional[datetime]
    reward: str
    team_count: int
    is_active: bool
    priority: int = 2

class CompetitionLister:
    """
    Fetches and ranks competitions from Kaggle API.
    Used to populate the competitions_registry.
    """

    def __init__(self):
        self.kaggle_service = KaggleService()

    def list_competitions(self, sort_by='latestDeadline', page=1) -> List[CompetitionMetadata]:
        """
        Fetch competitions from Kaggle.
        """
        try:
            client = self.kaggle_service.get_client()
            # api.competitions_list(page=1, category='all', sort_by='latestDeadline')
            comps = client.competitions_list(page=page, category='all', sort_by=sort_by)

            results = []
            for comp in comps:
                # Convert date
                deadline = getattr(comp, 'deadline', None)
                if deadline and hasattr(deadline, 'replace'):
                    deadline = deadline.replace(tzinfo=timezone.utc)

                # Determine priority based on heuristic
                priority = self._calculate_priority(comp)

                # Description often needs separate fetch, but list returns brief
                # Using 'ref' as slug

                meta = CompetitionMetadata(
                    slug=getattr(comp, 'ref', ''),
                    title=getattr(comp, 'title', ''),
                    description=getattr(comp, 'description', ''),
                    deadline=deadline,
                    reward=getattr(comp, 'reward', '0'),
                    team_count=int(getattr(comp, 'teamCount', 0)),
                    is_active=True, # Simplified
                    priority=priority
                )
                results.append(meta)

            return results

        except Exception as e:
            logger.error(f"Failed to list competitions: {e}")
            return []

    def _calculate_priority(self, comp) -> int:
        """
        1 = High (Active, Reward > 0, Teams > 500)
        2 = Medium (Active, Teams > 100)
        3 = Low (Others)
        """
        try:
            team_count = int(getattr(comp, 'teamCount', 0))
            reward = getattr(comp, 'reward', '0')
            has_reward = reward and reward != '0' and '$' in str(reward)

            # Simple heuristic
            if team_count > 500 and has_reward:
                return 1
            if team_count > 100:
                return 2
            return 3
        except Exception as e:
            logger.error(f"Failed to list competitions: {e}")
            return 3
