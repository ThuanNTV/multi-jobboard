from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class JobItem:
    title: str
    company: str
    location: str
    salary: Optional[str]
    posted_at: Optional[str]
    experience: str
    level: Optional[str]
    tags: List[str]
    url: str
    source: str
    description: Optional[str] = None

    def to_dict(self):
        return asdict(self)
